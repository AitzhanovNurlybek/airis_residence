"""
Перенос броней из Exely в свою базу — чтобы искать их по имени гостя.

Зачем это вообще. Гость, забывший номер брони, называет имя. А имя в Exely
доступно только детальным запросом по каждой броне: в списке лежат номер,
статус и дата изменения, больше ничего. Замерено 2026-08-29: одна деталь —
0,7 секунды, а броней у отеля тысяча. Двенадцать минут на полный обход, и
это при лимите Exely в десять запросов в секунду.

В переписке столько не ждут, поэтому имена собираются заранее.

Как устроен перенос.

**Список целиком, по страницам.** Exely отдаёт сводки порциями по тысяче,
от давно изменённых к свежим, и к каждой порции прикладывает continueToken.
Читаем все страницы: на 2026-10-05 это 6237 броней, 7 страниц, ~12 секунд.

**Только нужные брони.** Поиску по имени нужны ближайшие заезды и недавние
гости, а не прошлогодние отмены. Берём брони с заездом или созданием за
последние WINDOW_DAYS дней, ближайшие заезды — первыми.

**Порциями и по времени.** Детали читаются, пока не вышел бюджет запуска:
функция на Vercel живёт ограниченное время, и попытка перебрать всё разом
кончится обрывом на середине. Сохраняем после каждой пачки, так что
прерванный запуск не теряет сделанного.

**Мягко к чужому сервису.** Лимит Exely — десять запросов в секунду. Детали
идут в PARALLEL потоков с паузой, на деле около двух запросов в секунду:
упереться в лимит значит получить 429 и остаться без данных вовсе.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .booking_system.base import BookingSystemUnavailable
from .booking_system.exely_api import ExelyApi, _as_date, _first
from .db import ExelyBooking

logger = logging.getLogger(__name__)

#: Потолок броней за один запуск. Обычно раньше кончается время (BUDGET).
CHUNK = 150

#: Сколько детальных запросов идёт одновременно. Четыре потока с паузой
#: держатся далеко от лимита Exely в 10 запросов в секунду, и консьержу,
#: который ходит в Exely за тем же, квоты хватает.
PARALLEL = 4

#: Пауза после каждого детального запроса в своём потоке.
PAUSE = 0.2

#: Секунд от начала запуска, после которых новые детали не запрашиваются.
#: Список (все страницы) входит сюда же, а начатая пачка дочитывается.
#: Замер 2026-10-05 с живым Exely: 7 страниц ~12 с, затем около двух деталей
#: в секунду; при бюджете 40 запуск занял 45,7 с. Запуск в 30 секунд на
#: Vercel проходил и раньше; 35 держат весь запуск в пределах ~42 с.
BUDGET = 35.0

#: Какие брони нужны поиску по имени: заезд или создание не раньше, чем
#: столько дней назад. Остальные — история, гость о ней не спрашивает.
WINDOW_DAYS = 60

#: Защита от вечного цикла, если Exely вдруг всегда отвечает hasMoreData.
MAX_PAGES = 60


def _room(booking: dict[str, Any]) -> str:
    stays = booking.get("roomStays")
    if not isinstance(stays, list):
        return ""
    for stay in stays:
        if isinstance(stay, dict) and isinstance(stay.get("roomType"), dict):
            name = _first(stay["roomType"], "name", "title")
            if name:
                return str(name)
    return ""


def _dates(booking: dict[str, Any]) -> tuple[Any, Any]:
    stays = booking.get("roomStays")
    ins: list[Any] = []
    outs: list[Any] = []
    if isinstance(stays, list):
        for stay in stays:
            if not isinstance(stay, dict):
                continue
            dates = stay.get("stayDates")
            if isinstance(dates, dict):
                got_in = _as_date(dates.get("arrivalDateTime"))
                got_out = _as_date(dates.get("departureDateTime"))
                if got_in:
                    ins.append(got_in)
                if got_out:
                    outs.append(got_out)
    return (min(ins) if ins else None, max(outs) if outs else None)


def _name(booking: dict[str, Any]) -> str:
    who = booking.get("customer")
    if not isinstance(who, dict):
        return ""
    parts = [str(who.get(k) or "").strip() for k in ("lastName", "firstName")]
    return " ".join(p for p in parts if p)


def arrival_of(number: str) -> date | None:
    """Дата заезда из номера брони: 20261005-509506-1265394803 → 2026-10-05.

    Проверено на живых бронях 2026-10-05: первые восемь цифр — заезд, а не
    создание (бронь создана 4 октября, номер начинается с 20261005). При
    переносе дат номер, похоже, не меняется, поэтому при отборе смотрим ещё
    и на дату создания.
    """
    try:
        return date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    except (TypeError, ValueError):
        return None


async def summaries(api: ExelyApi, property_id: str) -> list[dict[str, Any]]:
    """Сводки всех броней — страница за страницей, по continueToken.

    2026-09-01 читали только первую страницу и решили, что Exely отдаёт одну
    тысячу самых старых броней (новее декабря 2025 в ней ничего), а свежие
    узнавали из уведомлений. Уведомления приходят пачкой раз в сутки и не обо
    всех бронях, поэтому 2026-10-05 гость с бронью на сегодня через
    Booking.com по фамилии не нашёлся. У каждой страницы есть continueToken и
    hasMoreData — с ними читаются все 6237 броней.
    """
    path = f"/v1/properties/{property_id}/bookings"
    rows: list[dict[str, Any]] = []
    token = ""
    for _ in range(MAX_PAGES):
        data = await api._get(path, {"continueToken": token} if token else None)
        rows.extend(r for r in api._rows(data) if isinstance(r, dict) and r.get("number"))
        if not isinstance(data, dict):
            break
        token = str(data.get("continueToken") or "")
        if not token or not data.get("hasMoreData"):
            break
    return rows


def _apply(record: ExelyBooking, booking: dict[str, Any]) -> None:
    """Переложить полную бронь из Exely в запись своей базы."""
    имя = _name(booking)
    заезд, выезд = _dates(booking)
    record.status = str(booking.get("status") or "")
    record.guest_name = имя
    record.guest_search = имя.casefold()
    record.check_in = заезд
    record.check_out = выезд
    record.room_name = _room(booking)
    try:
        record.total_amount = int(round(float(
            (booking.get("total") or {}).get("priceAfterTax"))))
    except (TypeError, ValueError):
        record.total_amount = 0
    record.modified_at = str(booking.get("modifiedDateTime") or "")


async def sync(session: AsyncSession, api: ExelyApi, property_id: str,
               limit: int = CHUNK, *, today: date | None = None,
               budget: float = BUDGET) -> dict[str, Any]:
    """Перенести очередную порцию броней: сначала ближайшие заезды."""
    started = time.monotonic()
    try:
        rows = await summaries(api, property_id)
    except BookingSystemUnavailable as error:
        return {"ok": False, "error": str(error)}

    if today is None:
        from .almaty import today as hotel_today  # noqa: PLC0415

        today = hotel_today()
    edge = today - timedelta(days=WINDOW_DAYS)

    def нужна(row: dict[str, Any]) -> bool:
        заезд = arrival_of(str(row["number"]))
        создана = str(row.get("createdDateTime") or "")[:10]
        return (заезд is not None and заезд >= edge) or создана >= edge.isoformat()

    known = {
        b.number: b
        for b in (await session.execute(select(ExelyBooking))).scalars().all()
    }

    # Статус есть прямо в сводке, и отмену видно без детального запроса.
    # Раньше отменённая бронь до перечитывания оставалась у нас «Active» —
    # и бот мог назвать гостю живой бронь, которой уже нет.
    статусов = 0
    for row in rows:
        record = known.get(str(row["number"]))
        status = str(row.get("status") or "")
        if record is not None and status and record.status != status:
            record.status = status
            статусов += 1

    очередь = [
        row for row in rows
        if нужна(row) and (
            str(row["number"]) not in known
            or known[str(row["number"])].modified_at != str(row.get("modifiedDateTime") or "")
        )
    ]
    # Ближайшие заезды первыми: гостю, который приезжает сегодня, бронь
    # нужнее, чем тому, кто приедет через месяц.
    очередь.sort(key=lambda r: abs(((arrival_of(str(r["number"])) or edge) - today).days))

    gate = asyncio.Semaphore(PARALLEL)

    async def деталь(number: str) -> dict[str, Any] | None:
        async with gate:
            try:
                full = await api._get(f"/v1/properties/{property_id}/bookings/{number}")
            except BookingSystemUnavailable as error:
                logger.warning("Бронь %s не прочиталась: %s", number, error)
                return None
            finally:
                await asyncio.sleep(PAUSE)
        booking = (full or {}).get("booking")
        return booking if isinstance(booking, dict) else None

    fetched = failed = 0
    очередь_сейчас = очередь[:limit]
    пачка = PARALLEL * 2
    for begin in range(0, len(очередь_сейчас), пачка):
        if time.monotonic() - started > budget:
            break
        part = очередь_сейчас[begin:begin + пачка]
        полные = await asyncio.gather(*(деталь(str(r["number"])) for r in part))
        for row, booking in zip(part, полные):
            if booking is None:
                failed += 1
                continue
            number = str(row["number"])
            record = known.get(number)
            if record is None:
                record = ExelyBooking(number=number)
                session.add(record)
                known[number] = record
            _apply(record, booking)
            fetched += 1
        # После каждой пачки: оборвись функция — сделанное не пропадёт.
        await session.commit()

    await session.commit()
    return {
        "ok": True,
        "перенесено": fetched,
        "статус обновлён": статусов,
        "не прочиталось": failed,
        "осталось в очереди": max(len(очередь) - fetched - failed, 0),
        "всего в Exely": len(rows),
        "уже у нас": len(known),
        "секунд": round(time.monotonic() - started, 1),
    }


async def remember(session: AsyncSession, api: ExelyApi, property_id: str,
                   number: str) -> bool:
    """Запомнить одну бронь по номеру — так, чтобы её нашли по имени гостя.

    Зовётся из уведомления Exely о новой брони: так бронь находится сразу, не
    дожидаясь ежечасного переноса (sync). Уведомления приходят пачкой раз в
    сутки и не обо всех бронях, а фоновая задача на Vercel может оборваться
    вместе с функцией, — поэтому это ускорение, а не основной путь.
    """
    try:
        full = await api._get(f"/v1/properties/{property_id}/bookings/{number}")
    except BookingSystemUnavailable as error:
        logger.warning("Бронь %s не прочиталась: %s", number, error)
        return False

    booking = (full or {}).get("booking")
    if not isinstance(booking, dict):
        return False

    record = await session.get(ExelyBooking, number)
    if record is None:
        record = ExelyBooking(number=number)
        session.add(record)
    _apply(record, booking)
    await session.commit()
    logger.info("Бронь %s запомнена: %s", number, record.guest_name or "без имени")
    return True


async def find_by_name(
    session: AsyncSession, name: str, limit: int = 5, *, arrival: date | None = None
) -> list[ExelyBooking]:
    """Брони по имени гостя.

    Имя — не пароль: однофамильцы встречаются, и по одному имени отдавать
    чужую бронь нельзя. Поэтому здесь только поиск; решение, показывать ли
    найденное, принимается выше и требует ещё и даты заезда.

    Каждое слово ищется отдельно: в Exely имя хранится «Фамилия Имя», а гость
    и бот пишут «James Gibson» — целой строкой такое не совпадёт. Слова короче
    трёх букв («Mr», «Ли») не участвуют: совпадут с половиной базы.
    """
    слова = [w for w in " ".join((name or "").split()).casefold().split() if len(w) >= 3]
    if not слова:
        return []

    query = select(ExelyBooking)
    for слово in слова:
        query = query.where(ExelyBooking.guest_search.contains(слово))
    if arrival is not None:
        query = query.where(ExelyBooking.check_in == arrival)
    rows = (
        await session.execute(query.order_by(ExelyBooking.check_in.desc()).limit(limit))
    ).scalars().all()
    return list(rows)
