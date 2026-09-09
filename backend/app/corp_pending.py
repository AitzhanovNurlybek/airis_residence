"""
Напоминание об авто-подтверждённых бронях, ещё не занесённых в Exely.

Партнёру уже сказали «да», а в шахматке брони нет и сама она там не
появится: Exely не создаёт брони извне. Пока её не занесли, номер выглядит
свободным — и его могут продать второй раз с сайта или с площадки.

Просьба «занесите в шахматку» уходит в WhatsApp вместе с бронью, но
сообщение уезжает вверх за полчаса. Поэтому здесь — не второе такое же
сообщение, а сводка: что до сих пор висит и сколько уже висит.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ ПОВТОРЯЕТСЯ, А НЕ НАПОМИНАЕТ ОДИН РАЗ

Однократное напоминание уместно там, где цена забывчивости — неудобство.
Здесь цена — двойная продажа номера, и она растёт с каждым часом. Пока
бронь не занесена, повод для напоминания никуда не делся, поэтому сводка
приходит на каждом запуске: раз в час в рабочее время. Занесли и нажали
«Занесено» — сводка исчезает сама.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Company, CorpBooking, CorpBookingItem, utcnow

logger = logging.getLogger(__name__)

#: Сколько ждать, прежде чем напоминать. Полчаса — чтобы не дёргать отель
#: по броне, которую прямо сейчас и заносят.
AFTER_MINUTES = 30


def _ждёт_минут(момент: Any) -> int:
    """Сколько минут прошло с подтверждения.

    Postgres отдаёт время с часовым поясом, SQLite — без него, и вычитание
    одного из другого падает. Сводка о риске двойной продажи не должна
    рушиться из-за того, какой базой пользуются на этой машине.
    """
    from datetime import timezone

    if момент is None:
        return 0
    if момент.tzinfo is None:
        момент = момент.replace(tzinfo=timezone.utc)
    return max(0, int((utcnow() - момент).total_seconds() // 60))


def _часов(минут: int) -> str:
    if минут < 60:
        return f"{минут} мин."
    часы = минут // 60
    хвост = "часа" if 2 <= часы % 10 <= 4 and часы not in (12, 13, 14) else (
        "час" if часы % 10 == 1 and часы != 11 else "часов")
    return f"{часы} {хвост}"


async def pending(session: AsyncSession) -> list[CorpBooking]:
    """Подтверждённые брони, которых ещё нет в шахматке."""
    граница = utcnow() - timedelta(minutes=AFTER_MINUTES)
    rows = (
        await session.execute(
            select(CorpBooking)
            .where(CorpBooking.auto_confirmed.is_(True))
            .where(CorpBooking.entered_at.is_(None))
            .where(CorpBooking.status.in_(("confirmed", "invoiced")))
            .where(CorpBooking.confirmed_at <= граница)
            .order_by(CorpBooking.confirmed_at)
        )
    ).scalars().all()
    return list(rows)


def describe(готовые: list[tuple[CorpBooking, str, str]]) -> str:
    """Сводка отелю. Одним сообщением, а не по одному на бронь."""
    lines = [
        f"🔴 Не занесено в Exely: {len(готовые)}",
        "",
        "Партнёрам уже подтверждено, а в шахматке этих броней нет.",
        "Пока не занесены — номер могут продать второй раз.",
        "",
    ]
    for booking, компания, блок in готовые:
        минут = _ждёт_минут(booking.confirmed_at)
        lines.append(f"• {booking.number} — {компания}, ждёт {_часов(минут)}")
        lines.append(блок)
        lines.append("")
    lines.append("Занесли — отметьте в админке, раздел «Заявки».")
    return "\n".join(lines)


async def run(session: AsyncSession, settings: Any, *,
              dry_run: bool = False) -> dict[str, Any]:
    """Напомнить отелю о том, что ещё не занесено."""
    from .lifecycle import quiet_hours

    брони = await pending(session)
    if not брони:
        return {"pending": 0}

    if quiet_hours():
        # Ночью не пишем: занести бронь всё равно некому, а разбуженный
        # человек к утру перестанет читать эти сообщения вовсе.
        return {"pending": len(брони), "note": "ночь — не пишем"}

    from .corp_api import exely_block

    ids = [b.id for b in брони]
    строки = (
        await session.execute(
            select(CorpBookingItem).where(CorpBookingItem.booking_id.in_(ids))
        )
    ).scalars().all()
    по_броням: dict[int, list[CorpBookingItem]] = {}
    for item in строки:
        по_броням.setdefault(item.booking_id, []).append(item)

    компании = {
        c.id: c.name
        for c in (
            await session.execute(
                select(Company).where(Company.id.in_({b.company_id for b in брони}))
            )
        ).scalars().all()
    }

    готовые = [
        (b, компании.get(b.company_id, ""),
         exely_block(b, по_броням.get(b.id, []), компании.get(b.company_id, "")))
        for b in брони
    ]
    текст = describe(готовые)

    if dry_run:
        return {"dry_run": True, "pending": len(брони), "text": текст}

    from .notify import _tell_hotel

    ушло = await _tell_hotel(текст, "брони, не занесённые в Exely")
    logger.info("Напоминание о %d незанесённых бронях, отправлено: %d",
                len(брони), ушло)
    return {"pending": len(брони), "sent": ушло}
