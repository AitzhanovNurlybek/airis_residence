"""
Брони без предоплаты: напомнить отелю позвонить, пока номер не простоял.

Бронь на сайте можно оформить без оплаты. Часть таких гостей приезжает,
часть — нет, и отель узнаёт об этом в день заезда, когда номер уже никому
не продать. Заказчица просила «через сутки ещё раз спросить: у вас бронь
стоит, вы же придёте».

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ СПРАШИВАЕТ ОТЕЛЬ, А НЕ БОТ

Гостю мы написать не можем, и это не выбор, а ограничение. Exely в данных
брони отдаёт только имя и фамилию — ни телефона, ни почты. Проверено на
живых бронях: поле `customer` содержит `firstName` и `lastName`, и всё.

Поэтому здесь не рассылка гостям, а сводка отелю: вот брони, за которые
никто не платил, вот имена и даты — позвоните. Контакты гостя у отеля есть
в кабинете Exely, просто не в API.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ ЧЕРЕЗ СУТКИ

Раньше — рано: человек мог отойти от компьютера и вернуться к оплате
вечером. Позже — поздно: чем ближе заезд, тем меньше шансов продать номер
заново.

Сутки проверяются один раз. Отметка о проверке хранится, и повторно та же
бронь в сводку не попадает: список, приходящий каждый день с одним и тем
же содержимым, перестают читать.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import BookingCheck, ExelyEvent, utcnow

logger = logging.getLogger(__name__)

#: Через сколько часов после создания брони проверять оплату.
AFTER_HOURS = 24

#: И до какого возраста имеет смысл проверять. Бронь недельной давности
#: либо уже оплачена, либо давно отменена — тревожить отель поздно.
UNTIL_HOURS = 96

#: Сколько броней разбирать за запуск. Каждая — отдельный запрос к Exely по
#: 0,7 секунды, а запуск живёт ограниченное время.
BATCH = 15


@dataclass
class Unpaid:
    """Бронь, за которую не заплатили."""

    number: str
    guest: str = ""
    dates: str = ""
    room: str = ""
    amount: int = 0


def _money(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


async def _to_check(session: AsyncSession, limit: int = BATCH) -> list[str]:
    """Брони, которым исполнились сутки и которые ещё не проверяли."""
    border = utcnow()
    rows = (
        await session.execute(
            select(ExelyEvent)
            .where(ExelyEvent.kind == "create_booking")
            .where(ExelyEvent.booking_number != "")
            .where(ExelyEvent.created_at <= border - timedelta(hours=AFTER_HOURS))
            .where(ExelyEvent.created_at >= border - timedelta(hours=UNTIL_HOURS))
            .order_by(ExelyEvent.created_at.desc())
        )
    ).scalars().all()

    known = {
        row.number
        for row in (await session.execute(select(BookingCheck))).scalars().all()
    }
    out: list[str] = []
    for event in rows:
        number = str(event.booking_number)
        if number in known or number in out:
            continue
        out.append(number)
        if len(out) >= limit:
            break
    return out


async def _look(settings: Any, number: str) -> tuple[str, Unpaid | None]:
    """Оплачена ли бронь. Возвращает (вердикт, данные если не оплачена)."""
    from .booking_system.exely_api import ExelyApi

    try:
        api = ExelyApi(settings.exely_client_id, settings.exely_client_secret,
                       settings.exely_property_id, auth_url=settings.exely_auth_url,
                       api_base=settings.exely_api_base)
        data = await api._get(
            f"/v1/properties/{settings.exely_property_id}/bookings/{number}")
    except Exception as error:  # noqa: BLE001 — одна нечитаемая бронь не повод падать
        # Отдельный вердикт, а не «gone». Разница решающая: «gone» означает
        # «разобрались, отель тревожить не о чем» и запоминается навсегда, а
        # здесь мы просто не дозвонились до Exely — у него бывают лимиты и
        # перебои. Пометив такую бронь проверенной, мы никогда бы к ней не
        # вернулись, и неоплаченная бронь тихо дожила бы до дня заезда.
        logger.warning("Бронь %s не прочиталась: %s", number, error)
        return "unreadable", None

    booking = (data or {}).get("booking") or {}
    if str(booking.get("status") or "").lower() != "active":
        # Отменённая бронь отелю уже не нужна.
        return "gone", None

    # Только брони с сайта отеля. С площадок (Booking и прочие) приходит
    # `source.type = Channel`, и «нет предоплаты» там означает не риск, а
    # обычный порядок: расчёт по правилам площадки, часто при заезде.
    #
    # Без этого отбора сводка сразу набрала десяток чужих броней на четверть
    # миллиона тенге — и отель перестал бы её читать на второй день.
    источник = str((booking.get("source") or {}).get("type") or "")
    if источник.lower() != "bookingengine":
        return "elsewhere", None

    prepaid = _money((booking.get("guaranteeInfo") or {}).get("totalPrepaid"))
    if prepaid > 0:
        return "paid", None

    who = booking.get("customer") or {}
    имя = " ".join(str(who.get(k) or "").strip()
                   for k in ("lastName", "firstName")).strip()
    stays = booking.get("roomStays") or []
    даты = комната = ""
    if stays and isinstance(stays[0], dict):
        сроки = stays[0].get("stayDates") or {}
        заезд = str(сроки.get("arrivalDateTime") or "")[:10]
        выезд = str(сроки.get("departureDateTime") or "")[:10]
        даты = f"{заезд} → {выезд}" if заезд else ""
        комната = str((stays[0].get("roomType") or {}).get("name") or "")

    return "unpaid", Unpaid(
        number=number, guest=имя, dates=даты, room=комната,
        amount=_money((booking.get("total") or {}).get("priceAfterTax")),
    )


def describe(found: list[Unpaid]) -> list[str]:
    """Сводка отелю. Одним сообщением, а не по одному на бронь."""
    lines = [
        f"Брони с сайта без предоплаты: {len(found)}",
        "",
        "Прошли сутки с бронирования, оплата не поступила. Стоит позвонить и",
        "подтвердить — иначе номер может простоять пустым.",
        "",
    ]
    for item in found:
        строка = f"• {item.number}"
        if item.guest:
            строка += f" — {item.guest}"
        lines.append(строка)
        подробности = " ".join(x for x in (item.dates, item.room) if x)
        if подробности:
            lines.append(f"  {подробности}")
        if item.amount:
            lines.append(f"  на сумму {item.amount} ₸")
    lines += ["", "Контакты гостей — в кабинете Exely: в API их нет."]
    return lines


async def run(session: AsyncSession, settings: Any, *, dry_run: bool = False) -> dict[str, Any]:
    """Проверить вчерашние брони и сообщить отелю о неоплаченных."""
    numbers = await _to_check(session)
    if not numbers:
        return {"checked": 0, "note": "суточных броней нет"}

    found: list[Unpaid] = []
    verdicts: dict[str, str] = {}
    for number in numbers:
        verdict, item = await _look(settings, number)
        verdicts[number] = verdict
        if item is not None:
            found.append(item)

    if dry_run:
        return {
            "dry_run": True,
            "checked": len(numbers),
            "verdicts": verdicts,
            "unpaid": [item.__dict__ for item in found],
        }

    # Отметки ставим независимо от отправки: сводка — не то, ради чего стоит
    # спрашивать Exely об одной броне повторно каждый час.
    for number, verdict in verdicts.items():
        # Непрочитанное не помечаем: вернёмся к нему следующим запуском.
        if verdict == "unreadable":
            continue
        if await session.get(BookingCheck, number) is None:
            session.add(BookingCheck(number=number, verdict=verdict))
    await session.commit()

    if not found:
        return {"checked": len(numbers), "unpaid": 0}

    # Сначала пробуем спросить самого гостя: он назвал имя в переписке, и по
    # нему бронь связывается с чатом. Это и просила заказчица — «через сутки
    # ещё раз спросить, точно приедете».
    спросили: list[str] = []
    остались: list[Unpaid] = []
    for item in found:
        if await _ask_guest(settings, item):
            спросили.append(item.number)
        else:
            остались.append(item)

    sent = 0
    if остались:
        from .notify import _tell_hotel

        sent = await _tell_hotel("\n".join(describe(остались)),
                                 "брони без предоплаты")
    logger.info("Броней без предоплаты: %d, спросили гостя: %d, отелю: %d",
                len(found), len(спросили), sent)
    return {"checked": len(numbers), "unpaid": len(found),
            "asked_guests": len(спросили), "sent_hotel": sent}


async def _ask_guest(settings: Any, item: Unpaid) -> bool:
    """Напомнить гостю о его броне, если знаем, в каком он чате.

    Связка идёт по имени: гость назвал его в переписке перед бронированием,
    и оно же стоит в броне. Другого мостика нет — Exely не отдаёт ни
    телефона, ни почты.

    Мостик не идеальный, поэтому два ограничения. Пишем только при
    ЕДИНСТВЕННОМ совпадении: однофамильцы существуют, и напомнить чужому
    человеку о чужой броне — значит выдать чужие данные. И пишем только о
    броне, ничего лишнего не раскрывая.
    """
    if not item.guest:
        return False

    from sqlalchemy import select

    from .db import GuestName, SessionLocal

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(GuestName).where(GuestName.name == item.guest.casefold())
            )
        ).scalars().all()

    чаты = {row.chat_id for row in rows}
    if len(чаты) != 1:
        # Ни одного или несколько — гостю не пишем.
        return False

    from .channels.whatsapp import WhatsAppChannel, WhatsAppError, for_whatsapp

    куда = f" на {item.dates}" if item.dates else ""
    текст = "\n".join([
        f"Здравствуйте! У вас оформлена бронь в Airis Residence{куда}.",
        "",
        "Оплата пока не поступила — подскажите, планы в силе? Если да, "
        "оплатить можно на сайте, а если что-то изменилось, просто "
        "напишите, и мы освободим номер.",
    ])
    try:
        channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
        await channel.send(list(чаты)[0], for_whatsapp(текст))
    except (WhatsAppError, Exception) as error:  # noqa: BLE001
        logger.warning("Гостю по броне %s не написали: %s", item.number, error)
        return False
    logger.info("Гость по броне %s спрошен напрямую", item.number)
    return True
