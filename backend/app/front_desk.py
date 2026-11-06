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
import re
from datetime import date, timedelta
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


_ВРЕМЯ = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?=\W|$)", re.I)
_НОЧЬ = re.compile(r"ноч|night|midnight|полуноч|рано утром|early morning|түн", re.I)
_ПОСЛЕ_ПОЛУДНЯ = re.compile(r"вечер|дня|после обеда|evening|afternoon|tonight|кешке|түстен кейін", re.I)


def early_arrival(time_text: str) -> bool:
    """Приезд ночью или до 9 утра: утренний список в 07:30 для него поздно.

    «около 2:00», «around 2am», «ночью, рейс в 3:40», «в 5 утра» — рано;
    «в 8 вечера», «около 10:00», «after 18:00» — нет.
    """
    text = time_text or ""
    if _НОЧЬ.search(text):
        return True
    совпадения = list(_ВРЕМЯ.finditer(text))
    if not совпадения:
        return False
    # Сначала «10:30» и «2am», потом голые числа: «в 5 утра».
    лучшее = next((m for m in совпадения if m.group(2) or m.group(3)), совпадения[0])
    час = int(лучшее.group(1))
    if час > 23:
        return False
    суффикс = (лучшее.group(3) or "").lower()
    if суффикс.startswith("p") and час < 12:
        час += 12
    elif суффикс.startswith("a") and час == 12:
        час = 0
    elif not суффикс and час < 12 and _ПОСЛЕ_ПОЛУДНЯ.search(text):
        час += 12
    return час < 9


async def save_note(*, chat_id: str, phone: str, guest_name: str, request: str,
                    booking_ref: str = "", room: str = "", arrival_date: date | None = None,
                    arrival_time: str = "", said: list[str] | None = None,
                    today: date | None = None, reminded: bool | None = None) -> bool:
    """Сохранить пометку.

    `reminded` — уже ли стойка об этом знает. Не задано — как раньше: на
    сегодня и без даты считаем, что уведомление в моменте и есть напоминание.
    """
    сегодня = today or hotel_today()
    if reminded is None:
        reminded = arrival_date is None or arrival_date <= сегодня
    try:
        async with SessionLocal() as session:
            session.add(FrontDeskNote(
                chat_id=chat_id[:80], phone=phone[:40], guest_name=guest_name[:120],
                booking_ref=booking_ref[:60], room=room[:20], arrival_date=arrival_date,
                arrival_time=arrival_time[:60], request=request[:1000],
                said="\n".join(str(x) for x in (said or []))[:2000],
                reminded=reminded,
            ))
            await session.commit()
        return True
    except Exception as error:  # noqa: BLE001
        logger.warning("Пометка для стойки не сохранилась: %s", error)
        return False


def _строка(n: int, note: FrontDeskNote) -> list[str]:
    кто = ", ".join(x for x in (note.guest_name, note.phone) if x) or "гость без имени"
    первая = f"{n}. {кто}" + (f" · бронь {note.booking_ref}" if note.booking_ref else "")
    lines = [первая]
    if note.arrival_time:
        lines.append(f"   ⏰ {note.arrival_time}")
    lines.append(f"   {note.request}")
    return lines


def digest_text(notes: list[FrontDeskNote], day: date,
                night: list[FrontDeskNote] | None = None) -> str:
    """Утренний список для стойки: кто сегодня, и кто приедет ночью или рано утром завтра."""
    lines = [f"🛎 Приезды — что гости заранее писали боту ({len(notes) + len(night or [])})", ""]
    if notes:
        lines.append(f"Сегодня, {day:%d.%m}:")
        for n, note in enumerate(notes, 1):
            lines += _строка(n, note)
        lines.append("")
    if night:
        lines.append(f"Ночью и рано утром {day + timedelta(days=1):%d.%m}:")
        for n, note in enumerate(night, len(notes) + 1):
            lines += _строка(n, note)
        lines.append("")
    lines.append("Переписка с каждым — в WhatsApp бота, в чате с гостем.")
    return "\n".join(lines).strip()


async def morning_digest(session: AsyncSession, *, today: date | None = None,
                         dry_run: bool = False) -> dict[str, Any]:
    """Утром в день приезда — список стойке. Повторный запуск ничего не шлёт."""
    сегодня = today or hotel_today()
    завтра = сегодня + timedelta(days=1)
    кандидаты = list((
        await session.execute(
            select(FrontDeskNote)
            .where(FrontDeskNote.arrival_date >= сегодня)
            .where(FrontDeskNote.arrival_date <= завтра)
            .where(FrontDeskNote.reminded.is_(False))
            .order_by(FrontDeskNote.id)
        )
    ).scalars().all())
    # Ночной приезд — накануне: в 07:30 его дня гость уже спит в номере.
    дневные = [n for n in кандидаты if n.arrival_date == сегодня]
    ночные = [n for n in кандидаты if n.arrival_date == завтра and early_arrival(n.arrival_time)]
    notes = дневные + ночные
    if not notes:
        return {"notes": 0, "sent": 0}
    текст = digest_text(дневные, сегодня, ночные)
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
