"""
Сообщения гостю по ходу брони: кто, когда и что получает.

Тексты живут в `guest_messages.py` — их правит отель. Здесь решается, когда
их отправлять и кому.

Два источника поводов.

**Событие от Exely.** Бронь создали или отменили — уведомление уже лежит в
таблице `exely_events` с пометкой `handled = false`. Отвечаем сразу.

**Календарь.** «Завтра заезд» и «вчера выезд» никакое событие не присылает —
это надо считать по датам самих броней. Раз в день проходим по известным
броням и смотрим, у кого завтра заезд, а у кого вчера был выезд.

Что здесь решается, кроме самой отправки.

**Одно сообщение на повод.** Пометка `handled` ставится ДО отправки. Если
отправка сорвётся, гость останется без сообщения — это неприятно. Если не
ставить, при повторном запуске он получит второе такое же — это хуже:
WhatsApp считает повторы спамом и блокирует номер отеля.

**Ночью молчим.** Сообщение в три часа ночи раздражает сильнее, чем
радует, а гость на него всё равно не ответит. Всё, что выпало на ночь,
ждёт утра.

**Без телефона не отправляем.** Бронь могли завести на стойке или с
агрегатора, где номера нет. Молча пропускаем — писать некуда.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .almaty import now as hotel_now, today as hotel_today
from .booking_system.exely_api import _as_date, _first
from .channels.whatsapp import WhatsAppChannel, WhatsAppError, for_whatsapp
from .db import ExelyEvent
from .guest_messages import (
    AFTER_DEPARTURE,
    BEFORE_ARRIVAL,
    EVENT_MESSAGES,
    render,
)

logger = logging.getLogger(__name__)

#: Часы, когда можно писать гостю (время Алматы).
QUIET_BEFORE = 9
QUIET_AFTER = 21

#: Насколько глубоко в прошлое смотрим на календарные поводы. Больше недели
#: назад напоминать не о чем, а перебирать всю историю каждый день незачем.
LOOKBACK_DAYS = 30


@dataclass
class Planned:
    """Одно готовое к отправке сообщение."""

    phone: str
    text: str
    reason: str
    event_id: int | None = None


def quiet_hours(hour: int | None = None) -> bool:
    """Сейчас ночь и писать не надо?"""
    current = hotel_now().hour if hour is None else hour
    return current < QUIET_BEFORE or current >= QUIET_AFTER


def _facts(event: ExelyEvent) -> dict[str, Any]:
    """Разобрать сохранённое тело уведомления."""
    try:
        payload = json.loads(event.payload or "{}")
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    # У Exely полезное лежит то на верхнем уровне, то под ключом booking.
    inner = payload.get("booking") or payload.get("reservation")
    return inner if isinstance(inner, dict) else payload


def _guest_name(data: dict[str, Any]) -> str:
    """Имя для обращения — одно слово.

    Обращаться «Иванов Иван Иванович, спасибо за бронирование» нельзя, это
    звучит как повестка. Берём firstName, если он пришёл отдельным полем, а
    из слитного имени — первое слово: в «Пётр Тестов» имя стоит первым.
    """
    for key in ("guest", "customer", "mainGuest"):
        who = data.get(key)
        if not isinstance(who, dict):
            continue
        first = who.get("firstName")
        if first:
            return str(first).strip().split()[0]
        whole = _first(who, "fullName", "name")
        if whole:
            return str(whole).strip().split()[0]
    return ""


def _dates(data: dict[str, Any]) -> tuple[date | None, date | None]:
    check_in = _as_date(_first(data, "arrivalDate", "checkInDate", "checkIn", "startDate"))
    check_out = _as_date(_first(data, "departureDate", "checkOutDate", "checkOut", "endDate"))
    if check_in and check_out:
        return check_in, check_out
    stays = data.get("roomStays")
    if isinstance(stays, list):
        ins = [d for s in stays if isinstance(s, dict)
               for d in [_as_date(_first(s, "arrivalDate", "checkInDate", "checkIn"))] if d]
        outs = [d for s in stays if isinstance(s, dict)
                for d in [_as_date(_first(s, "departureDate", "checkOutDate", "checkOut"))] if d]
        return (min(ins) if ins else check_in, max(outs) if outs else check_out)
    return check_in, check_out


def _room_name(data: dict[str, Any]) -> str:
    """Название категории из брони.

    Лежит внутри roomStays[].roomType и приходит то строкой, то объектом с
    именем. Не нашли — возвращаем пусто: шаблон переживёт, а выдумывать
    категорию за отель нельзя.
    """
    stays = data.get("roomStays")
    if not isinstance(stays, list):
        return ""
    for stay in stays:
        if not isinstance(stay, dict):
            continue
        room = stay.get("roomType")
        if isinstance(room, dict):
            name = _first(room, "name", "title", "displayName")
            if name:
                return str(name)
        elif isinstance(room, str) and not room.isdigit():
            return room
    return ""


def _values(event: ExelyEvent, settings: Any) -> dict[str, Any]:
    """Подстановки для шаблона."""
    data = _facts(event)
    check_in, check_out = _dates(data)
    nights = (check_out - check_in).days if check_in and check_out else 0
    return {
        "name": _guest_name(data),
        "number": event.booking_number,
        "check_in": check_in.strftime("%d.%m") if check_in else "",
        "check_out": check_out.strftime("%d.%m") if check_out else "",
        "nights": nights or "",
        # Категория приходит в скобках и с ведущим пробелом или не приходит
        # вовсе: так пустое значение не оставляет в тексте висячих запятых.
        "room": f" ({_room_name(data)})" if _room_name(data) else "",
        "phone": getattr(settings, "hotel_phone", "") or "+7 (777) 531-00-09",
        "check_in_time": "14:00",
    }


async def plan_from_events(session: AsyncSession, settings: Any) -> list[Planned]:
    """Что отправить по свежим уведомлениям Exely."""
    rows = (
        await session.execute(
            select(ExelyEvent)
            .where(ExelyEvent.handled.is_(False))
            .order_by(ExelyEvent.id)
            .limit(50)
        )
    ).scalars().all()

    planned: list[Planned] = []
    for event in rows:
        template = EVENT_MESSAGES.get(event.kind.strip().casefold().replace(" ", ""))
        if not template:
            # Событие нам не интересно (заезд, выезд, смена комнаты).
            # Помечаем обработанным, иначе оно будет всплывать вечно.
            event.handled = True
            continue
        if not event.guest_phone:
            logger.info("Событие %s без телефона — писать некуда", event.id)
            event.handled = True
            continue
        values = _values(event, settings)
        # Без дат сообщение вырождается в «Бронь X:, заезд, выезд .» —
        # такое гостю слать нельзя. Значит уведомление пришло в форме, под
        # которую разбор не написан: помечаем обработанным и сообщаем в лог,
        # чтобы поправить разбор по живому примеру.
        if not values["check_in"] or not values["check_out"]:
            logger.warning(
                "Событие %s (%s): в теле нет дат — сообщение не собрать, "
                "проверь разбор под реальный формат Exely",
                event.id, event.booking_number,
            )
            event.handled = True
            continue

        planned.append(
            Planned(
                phone=event.guest_phone,
                text=render(template, **values),
                reason=f"{event.kind} по броне {event.booking_number}",
                event_id=event.id,
            )
        )
    return planned


async def plan_from_calendar(session: AsyncSession, settings: Any) -> list[Planned]:
    """Напоминания, которые считаются по датам, а не приходят событием.

    Опираемся на брони, о которых знаем из уведомлений: завтрашний заезд и
    вчерашний выезд. Пометка о том, что напоминание уже ушло, хранится в том
    же `event_key` — отдельной таблицы под это заводить не стали, поводов
    два на бронь.
    """
    today = hotel_today()
    since = today - timedelta(days=LOOKBACK_DAYS)

    rows = (
        await session.execute(
            select(ExelyEvent)
            .where(ExelyEvent.created_at >= since)
            .where(ExelyEvent.booking_number != "")
            .order_by(ExelyEvent.id.desc())
            .limit(500)
        )
    ).scalars().all()

    # Одна бронь — одно последнее состояние. Отменённые пропускаем.
    latest: dict[str, ExelyEvent] = {}
    cancelled: set[str] = set()
    for event in rows:
        kind = event.kind.strip().casefold()
        if "cancel" in kind:
            cancelled.add(event.booking_number)
        latest.setdefault(event.booking_number, event)

    already = {
        e.event_key for e in rows if e.event_key.startswith(("напоминание:", "отзыв:"))
    }

    planned: list[Planned] = []
    for number, event in latest.items():
        if number in cancelled or not event.guest_phone:
            continue
        data = _facts(event)
        check_in, check_out = _dates(data)
        values = _values(event, settings)

        if check_in == today + timedelta(days=1) and f"напоминание:{number}" not in already:
            planned.append(Planned(event.guest_phone, render(BEFORE_ARRIVAL, **values),
                                   f"завтра заезд по броне {number}"))
        if check_out == today - timedelta(days=1) and f"отзыв:{number}" not in already:
            planned.append(Planned(event.guest_phone, render(AFTER_DEPARTURE, **values),
                                   f"вчера выезд по броне {number}"))
    return planned


async def run(session: AsyncSession, settings: Any, *, dry_run: bool = False) -> dict[str, Any]:
    """Разобрать поводы и отправить сообщения."""
    if quiet_hours():
        return {"skipped": "ночь — сообщения ждут утра", "hour": hotel_now().hour}

    planned = await plan_from_events(session, settings)

    # Бронь, созданная накануне заезда, попадает сразу в оба списка: и
    # «спасибо за бронирование», и «завтра ждём». Гость получил бы два
    # сообщения подряд — ровно то, за что WhatsApp блокирует номера.
    # Подтверждение важнее: в нём все детали, включая завтрашнюю дату.
    just_confirmed = {p.reason.split()[-1] for p in planned}
    for item in await plan_from_calendar(session, settings):
        if item.reason.split()[-1] in just_confirmed:
            logger.info("Пропускаю «%s»: подтверждение брони уже уходит", item.reason)
            continue
        planned.append(item)

    await session.commit()

    if dry_run:
        return {
            "dry_run": True,
            "planned": [{"phone": p.phone[-4:], "reason": p.reason, "text": p.text}
                        for p in planned],
        }

    if not planned:
        return {"sent": 0, "note": "поводов нет"}

    try:
        channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
    except WhatsAppError as error:
        logger.warning("Рассылка невозможна: %s", error)
        return {"sent": 0, "error": str(error)}

    sent = 0
    for item in planned:
        # Пометка ДО отправки: повтор хуже пропуска (см. заголовок модуля).
        if item.event_id is not None:
            event = await session.get(ExelyEvent, item.event_id)
            if event:
                event.handled = True
        else:
            session.add(ExelyEvent(
                event_key=("напоминание:" if "заезд" in item.reason else "отзыв:")
                          + item.reason.split()[-1],
                kind="lifecycle",
                booking_number=item.reason.split()[-1],
                guest_phone=item.phone,
                payload="",
                handled=True,
            ))
        await session.commit()

        try:
            await channel.send(f"{''.join(c for c in item.phone if c.isdigit())}@c.us",
                               for_whatsapp(item.text))
            sent += 1
            logger.info("Отправлено: %s", item.reason)
        except WhatsAppError as error:
            logger.warning("Не отправилось (%s): %s", item.reason, error)

    return {"sent": sent, "planned": len(planned)}
