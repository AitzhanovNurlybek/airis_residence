"""
Перенос броней из Exely в свою базу — чтобы искать их по имени гостя.

Зачем это вообще. Гость, забывший номер брони, называет имя. А имя в Exely
доступно только детальным запросом по каждой броне: в списке лежат номер,
статус и дата изменения, больше ничего. Замерено 2026-08-29: одна деталь —
0,7 секунды, а броней у отеля тысяча. Двенадцать минут на полный обход, и
это при лимите Exely в десять запросов в секунду.

В переписке столько не ждут, поэтому имена собираются заранее.

Как устроен перенос.

**Порциями.** За один запуск обрабатывается небольшая пачка. Функция на
Vercel живёт ограниченное время, и попытка перебрать всё разом кончится
обрывом на середине.

**С места, где остановились.** Порядок обхода — от недавно изменённых к
старым: свежая бронь нужнее гостю, чем прошлогодняя. Уже перенесённые и не
менявшиеся с тех пор пропускаются, поэтому второй проход почти мгновенный.

**Мягко к чужому сервису.** Между запросами выдерживается пауза: лимит
Exely — десять деталей в секунду, и упереться в него значит получить 429 и
остаться без данных вовсе.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .booking_system.base import BookingSystemUnavailable
from .booking_system.exely_api import ExelyApi, _as_date, _first
from .db import ExelyBooking

logger = logging.getLogger(__name__)

#: Сколько броней разбирать за один запуск. Сорок штук — это около тридцати
#: секунд с паузами, что укладывается в время жизни функции с запасом.
CHUNK = 40

#: Пауза между детальными запросами. Лимит Exely — 10 в секунду; берём вдвое
#: реже, чтобы не соревноваться с самим консьержем за ту же квоту.
PAUSE = 0.2


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


async def sync(session: AsyncSession, api: ExelyApi, property_id: str,
               limit: int = CHUNK) -> dict[str, Any]:
    """Перенести очередную порцию броней."""
    try:
        data = await api._get(f"/v1/properties/{property_id}/bookings")
    except BookingSystemUnavailable as error:
        return {"ok": False, "error": str(error)}

    rows = [r for r in api._rows(data) if isinstance(r, dict) and r.get("number")]
    # Свежие сначала: гостю нужнее его завтрашняя бронь, а не прошлогодняя.
    rows.sort(key=lambda r: str(r.get("modifiedDateTime") or ""), reverse=True)

    known = {
        b.number: b.modified_at
        for b in (await session.execute(select(ExelyBooking))).scalars().all()
    }

    fetched = skipped = failed = 0
    for row in rows:
        if fetched >= limit:
            break
        number = str(row["number"])
        modified = str(row.get("modifiedDateTime") or "")
        # Уже перенесена и с тех пор не менялась — трогать незачем.
        if known.get(number) == modified and modified:
            skipped += 1
            continue

        try:
            full = await api._get(f"/v1/properties/{property_id}/bookings/{number}")
        except BookingSystemUnavailable as error:
            logger.warning("Бронь %s не прочиталась: %s", number, error)
            failed += 1
            continue

        booking = (full or {}).get("booking")
        if not isinstance(booking, dict):
            failed += 1
            continue

        name = _name(booking)
        check_in, check_out = _dates(booking)
        total = (booking.get("total") or {}).get("priceAfterTax")

        record = await session.get(ExelyBooking, number)
        if record is None:
            record = ExelyBooking(number=number)
            session.add(record)
        record.status = str(booking.get("status") or "")
        record.guest_name = name
        record.guest_search = name.casefold()
        record.check_in = check_in
        record.check_out = check_out
        record.room_name = _room(booking)
        try:
            record.total_amount = int(round(float(total)))
        except (TypeError, ValueError):
            record.total_amount = 0
        record.modified_at = modified

        fetched += 1
        await asyncio.sleep(PAUSE)

    await session.commit()
    total_known = len(known) + fetched
    return {
        "ok": True,
        "перенесено": fetched,
        "без изменений": skipped,
        "не прочиталось": failed,
        "всего в Exely": len(rows),
        "уже у нас": total_known,
    }


async def remember(session: AsyncSession, api: ExelyApi, property_id: str,
                   number: str) -> bool:
    """Запомнить одну бронь по номеру — так, чтобы её нашли по имени гостя.

    Появилось потому, что перенос списком не работает. Проверено на боевом
    2026-09-01: `/bookings` отдаёт ровно тысячу САМЫХ СТАРЫХ броней — новее
    5 декабря 2025 в нём нет ничего, — и никакие параметры на это не влияют:
    ни offset, ни page, ни фильтры по датам создания и заезда. Все шесть
    вариантов вернули один и тот же список.

    Значит гостя, забывшего номер брони, поиск по имени не нашёл бы вовсе:
    в базе лежали бы только прошлогодние отменённые.

    Зато номер каждой новой брони приходит уведомлением, а по номеру
    Exely отдаёт всё. Отсюда и способ: запоминаем бронь в момент, когда
    узнали о ней, а не пытаемся вычитать задним числом.
    """
    try:
        full = await api._get(f"/v1/properties/{property_id}/bookings/{number}")
    except BookingSystemUnavailable as error:
        logger.warning("Бронь %s не прочиталась: %s", number, error)
        return False

    booking = (full or {}).get("booking")
    if not isinstance(booking, dict):
        return False

    имя = _name(booking)
    заезд, выезд = _dates(booking)
    record = await session.get(ExelyBooking, number)
    if record is None:
        record = ExelyBooking(number=number)
        session.add(record)
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
    await session.commit()
    logger.info("Бронь %s запомнена: %s", number, имя or "без имени")
    return True


async def find_by_name(
    session: AsyncSession, name: str, limit: int = 5
) -> list[ExelyBooking]:
    """Брони по имени гостя.

    Имя — не пароль: однофамильцы встречаются, и по одному имени отдавать
    чужую бронь нельзя. Поэтому здесь только поиск; решение, показывать ли
    найденное, принимается выше и требует ещё и даты заезда.
    """
    needle = " ".join((name or "").split()).casefold()
    if len(needle) < 3:
        return []

    rows = (
        await session.execute(
            select(ExelyBooking)
            .where(ExelyBooking.guest_search.contains(needle))
            .order_by(ExelyBooking.check_in.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)
