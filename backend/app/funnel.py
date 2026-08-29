"""
Воронка: докуда доходят гости, которые написали в WhatsApp.

Отель видит, что бот отвечает, и на этом знание кончается. Сколько человек
написало за неделю, сколько дошло до цен, сколько получило ссылку на бронь и
сколько молча ушло — не видно нигде. А это единственные цифры, по которым
можно понять, приносит бот деньги или просто вежливо разговаривает.

────────────────────────────────────────────────────────────────────────
ОТКУДА БЕРУТСЯ СТАДИИ

Не из догадок модели, а из следов в самой переписке. Каждый вызов
инструмента ложится в историю строкой с именем: `check_availability` —
гостю показали свободные номера и цены, `booking_link` — довели до формы
бронирования. Поэтому стадия считается точно и бесплатно: ни одного
обращения к модели, сколько бы разговоров ни было.

**Стадия — это максимум, которого разговор достиг.** Гость, получивший
ссылку, уже прошёл проверку наличия, и в верхних этапах он тоже считается.
Иначе воронка перестаёт быть воронкой: сумма этапов должна расти снизу
вверх, а не делить людей на непересекающиеся кучки.

**Чем закончилось — отдельно от того, докуда дошли.** Гость может дойти до
ссылки и пропасть, а может дойти до цен и продолжать писать. Смешав это в
один список, получаешь цифры, из которых непонятно, что делать.

────────────────────────────────────────────────────────────────────────
ЧЕГО ЗДЕСЬ НЕТ

**Брони.** Соблазн показать «забронировал» велик, но честно посчитать это
нечем: бронь оформляется на стороне Exely, а телефон гостя Exely в ответах
не отдаёт — связать переписку с бронью не по чему. Показывать сюда
придуманное число хуже, чем не показывать никакого: на него станут
смотреть. Последний измеримый этап — «довели до формы», дальше смотреть
надо в Exely.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import DialogFollowup, DialogMessage, utcnow

logger = logging.getLogger(__name__)

CHANNEL = "whatsapp"

#: За какой срок считаем по умолчанию. Две недели: достаточно, чтобы цифры
#: не прыгали от одного разговора, и достаточно мало, чтобы отражать то, как
#: бот работает сейчас, а не полгода назад.
DEFAULT_DAYS = 14

#: Сколько часов тишины считать уходом. Совпадает с порогом дожима не
#: случайно: это один и тот же момент — гость перестал отвечать.
SILENT_HOURS = 2


@dataclass
class Talk:
    """Один разговор в разрезе воронки."""

    chat_id: str
    phone: str
    messages: int = 0
    guest_messages: int = 0
    saw_prices: bool = False
    got_link: bool = False
    asked_photos: bool = False
    looked_up_booking: bool = False
    nudges: int = 0
    started: datetime | None = None
    last: datetime | None = None
    last_role: str = ""

    @property
    def stage(self) -> str:
        """Докуда дошёл разговор. Максимум, а не последнее действие."""
        if self.got_link:
            return "довели до формы"
        if self.saw_prices:
            return "показали цены"
        return "просто написал"

    @property
    def silent_hours(self) -> int:
        if self.last is None:
            return 0
        border = utcnow()
        said = self.last if self.last.tzinfo else self.last.replace(tzinfo=border.tzinfo)
        return int((border - said).total_seconds() // 3600)

    @property
    def outcome(self) -> str:
        """Чем кончилось — отдельно от того, докуда дошли."""
        if self.last_role == "user":
            return "ждёт ответа"
        if self.silent_hours < SILENT_HOURS:
            return "идёт"
        return "молчит"


def _tool_names(content: str) -> set[str]:
    """Какие инструменты названы в этой записи истории."""
    raw = (content or "").strip()
    if not raw.startswith("["):
        return set()
    try:
        parsed = json.loads(raw)
    except ValueError:
        return set()
    if not isinstance(parsed, list):
        return set()
    return {
        str(block.get("name"))
        for block in parsed
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name")
    }


def _phone(chat_id: str) -> str:
    digits = "".join(ch for ch in str(chat_id) if ch.isdigit())
    return f"+{digits}" if digits else str(chat_id)


async def collect(session: AsyncSession, days: int = DEFAULT_DAYS) -> list[Talk]:
    """Разобрать переписку за срок по разговорам."""
    since = utcnow() - timedelta(days=max(1, days))

    rows = (
        await session.execute(
            select(DialogMessage)
            .where(DialogMessage.channel == CHANNEL)
            .where(DialogMessage.created_at >= since)
            .order_by(DialogMessage.id)
        )
    ).scalars().all()

    talks: dict[str, Talk] = {}
    for row in rows:
        talk = talks.get(row.chat_id)
        if talk is None:
            talk = Talk(chat_id=row.chat_id, phone=_phone(row.chat_id), started=row.created_at)
            talks[row.chat_id] = talk

        # Записи с вызовами инструментов — служебные: гость их не видел, и в
        # счётчик сообщений они не идут. Иначе один вопрос про наличие
        # выглядит как переписка из пяти реплик.
        tools = _tool_names(row.content)
        if tools:
            talk.saw_prices |= "check_availability" in tools
            talk.got_link |= "booking_link" in tools
            talk.asked_photos |= "room_page" in tools
            talk.looked_up_booking |= bool(tools & {"find_booking", "find_by_name"})
        elif not row.content.strip().startswith("["):
            talk.messages += 1
            if row.role == "user":
                talk.guest_messages += 1
            talk.last = row.created_at
            talk.last_role = row.role

    if talks:
        marks = (
            await session.execute(
                select(DialogFollowup)
                .where(DialogFollowup.channel == CHANNEL)
                .where(DialogFollowup.sent_at >= since)
            )
        ).scalars().all()
        for mark in marks:
            if mark.chat_id in talks:
                talks[mark.chat_id].nudges += 1

    return sorted(talks.values(), key=lambda t: t.last or t.started or since, reverse=True)


def summarize(talks: list[Talk]) -> dict[str, Any]:
    """Свести разговоры в воронку и потери."""
    total = len(talks)
    prices = sum(1 for t in talks if t.saw_prices)
    link = sum(1 for t in talks if t.got_link)

    def share(part: int) -> int:
        return round(part * 100 / total) if total else 0

    # Этапы идут сверху вниз и вложены друг в друга: получивший ссылку учтён
    # и в «показали цены». Так видно, где именно теряются люди.
    stages = [
        {"этап": "написали", "сколько": total, "доля": 100},
        {"этап": "показали цены", "сколько": prices, "доля": share(prices)},
        {"этап": "довели до формы", "сколько": link, "доля": share(link)},
    ]

    # Потери — это не «сколько не дошло», а «кто именно и на чём застрял».
    # По списку можно позвонить, по проценту нельзя.
    lost = [t for t in talks if t.outcome == "молчит"]
    waiting = [t for t in talks if t.outcome == "ждёт ответа"]

    return {
        "разговоров": total,
        "этапы": stages,
        "потеряли_после_цен": sum(1 for t in lost if t.saw_prices and not t.got_link),
        "потеряли_после_ссылки": sum(1 for t in lost if t.got_link),
        "молчат": len(lost),
        "ждут_ответа": len(waiting),
        "дожали": sum(1 for t in talks if t.nudges),
        "спрашивали_фото": sum(1 for t in talks if t.asked_photos),
        "искали_свою_бронь": sum(1 for t in talks if t.looked_up_booking),
    }


async def report(session: AsyncSession, days: int = DEFAULT_DAYS) -> dict[str, Any]:
    """Воронка целиком: цифры и разговоры за ними."""
    talks = await collect(session, days)
    return {
        "дней": days,
        **summarize(talks),
        "разговоры": [
            {
                "телефон": t.phone,
                "этап": t.stage,
                "состояние": t.outcome,
                "сообщений": t.messages,
                "от гостя": t.guest_messages,
                "молчит часов": t.silent_hours,
                "дожатий": t.nudges,
            }
            for t in talks
        ],
    }
