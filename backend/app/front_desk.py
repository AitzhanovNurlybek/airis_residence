"""
Что гость сообщил боту для стойки: хранение и утреннее напоминание.

2026-10-15 отель пожаловался: гость пишет «приедем пораньше, сумки
оставим», бот отвечает, а ресепшен в день приезда «хлопает глазами, кто там
писал». Уведомление уходит стойке сразу (notify.notify_front_desk), но
сообщение, пришедшее за три дня, в день приезда никто не найдёт: смена
другая, чат длинный.

Поэтому пометка с днём приезда хранится, и утром этого дня стойке приходит
список: кто сегодня приезжает и что ему обещано. Одно сообщение на утро, а
не по сообщению на гостя: десять уведомлений подряд перестают читать.

Пометка на сегодня или на прошлое напоминанием не дублируется: уведомление
в моменте и есть напоминание.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .almaty import today as hotel_today
from .db import FrontDeskNote, SessionLocal

logger = logging.getLogger(__name__)


def arrival_words(day: date | None, time: str = "") -> str:
    """«17.10, около 10:00» — день и время приезда так, как их прочтёт стойка."""
    части = []
    if day:
        части.append(f"{day:%d.%m}")
    if time:
        части.append(time)
    return ", ".join(части)


async def save_note(*, chat_id: str, phone: str, guest_name: str, request: str,
                    booking_ref: str = "", room: str = "", arrival_date: date | None = None,
                    arrival_time: str = "", said: list[str] | None = None,
                    today: date | None = None) -> bool:
    """Сохранить пометку. Не вышло — не беда: стойке уже ушло уведомление."""
    сегодня = today or hotel_today()
    try:
        async with SessionLocal() as session:
            session.add(FrontDeskNote(
                chat_id=chat_id[:80], phone=phone[:40], guest_name=guest_name[:120],
                booking_ref=booking_ref[:60], room=room[:20], arrival_date=arrival_date,
                arrival_time=arrival_time[:60], request=request[:1000],
                said="\n".join(str(x) for x in (said or []))[:2000],
                # Сегодня и раньше напоминать утром уже некогда — уведомление
                # в моменте ушло только что.
                reminded=arrival_date is None or arrival_date <= сегодня,
            ))
            await session.commit()
        return True
    except Exception as error:  # noqa: BLE001
        logger.warning("Пометка для стойки не сохранилась: %s", error)
        return False


def digest_text(notes: list[FrontDeskNote], day: date) -> str:
    """Утренний список для стойки."""
    lines = [f"🛎 Сегодня, {day:%d.%m}, приезжают — что гости заранее писали боту", ""]
    for n, note in enumerate(notes, 1):
        кто = ", ".join(x for x in (note.guest_name, note.phone) if x) or "гость без имени"
        lines.append(f"{n}. {кто}")
        if note.booking_ref:
            lines.append(f"   Бронь: {note.booking_ref}")
        if note.arrival_time:
            lines.append(f"   Приезд: {note.arrival_time}")
        lines.append(f"   Что передать: {note.request}")
        lines.append("")
    lines.append("Переписка с каждым — в WhatsApp отеля, в чате с гостем.")
    return "\n".join(lines).strip()


async def morning_digest(session: AsyncSession, *, today: date | None = None,
                         dry_run: bool = False) -> dict[str, Any]:
    """Утром в день приезда — список стойке. Повторный запуск ничего не шлёт."""
    сегодня = today or hotel_today()
    notes = list((
        await session.execute(
            select(FrontDeskNote)
            .where(FrontDeskNote.arrival_date == сегодня)
            .where(FrontDeskNote.reminded.is_(False))
            .order_by(FrontDeskNote.id)
        )
    ).scalars().all())
    if not notes:
        return {"notes": 0, "sent": 0}
    текст = digest_text(notes, сегодня)
    if dry_run:
        return {"dry_run": True, "notes": len(notes), "text": текст}

    from .notify import _tell_hotel  # noqa: PLC0415 — notify тянет каналы

    ушло = await _tell_hotel(текст, "приезды на сегодня", corporate=True)
    if ушло:
        # Отмечаем только доставленное: не ушло — попробует следующий запуск.
        for note in notes:
            note.reminded = True
        await session.commit()
    logger.info("Утренний список для стойки: пометок %d, отправлено %d", len(notes), ушло)
    return {"notes": len(notes), "sent": ушло}
