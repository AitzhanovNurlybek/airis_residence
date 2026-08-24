"""
История переписки: чем консьерж помнит разговор.

Разговор в мессенджере не заканчивается. Гость спросил цену, ушёл на полдня,
вернулся с «а на выходные?» — и это продолжение того же разговора, а не новый.
Без истории консьерж переспрашивал бы имя и даты по кругу.

Двух вещей здесь нарочно нет.

Не храним разговор целиком навсегда: в запрос к модели уходят последние
несколько реплик, а старое лежит только для разбора спорных случаев. Длинная
история дорога в токенах на каждом сообщении и вредна по существу — модель
начинает цепляться за детали недельной давности.

Не считаем разговор оконченным. У переписки нет кнопки «завершить», и попытка
угадать конец («полчаса молчит — значит всё») чаще ошибается, чем помогает.
Вместо этого — срок давности: реплики старше суток в новый запрос не
подмешиваются, но из базы не исчезают.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .almaty import now as hotel_now
from .db import ChannelReceipt, DialogMessage

logger = logging.getLogger(__name__)

#: Сколько ждать продолжения, прежде чем считать разговор прошлым.
#: Сутки — потому что гость пишет вечером и возвращается утром, и это всё ещё
#: та же поездка. Через неделю разговор точно про другое.
CONTINUES_FOR = timedelta(hours=24)


async def load_history(
    sessions: async_sessionmaker[AsyncSession],
    channel: str,
    chat_id: str,
    depth: int = 12,
) -> list[dict[str, Any]]:
    """Последние реплики в том виде, в каком их ждёт модель."""
    since = hotel_now() - CONTINUES_FOR
    async with sessions() as session:
        rows = (
            await session.execute(
                select(DialogMessage)
                .where(
                    DialogMessage.channel == channel,
                    DialogMessage.chat_id == chat_id,
                    DialogMessage.created_at >= since,
                )
                .order_by(DialogMessage.id.desc())
                .limit(max(0, depth))
            )
        ).scalars().all()

    history: list[dict[str, Any]] = []
    for row in reversed(rows):
        try:
            content = json.loads(row.content)
        except ValueError:
            content = row.content
        history.append({"role": row.role, "content": content})

    # Модель не примет историю, которая начинается с её собственной реплики:
    # разговор обязан открываться словами гостя.
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


async def save_turn(
    sessions: async_sessionmaker[AsyncSession],
    channel: str,
    chat_id: str,
    messages: list[dict[str, Any]],
    already: int,
) -> None:
    """
    Дописать то, что появилось за этот ход.

    `messages` — полная переписка после ответа, `already` — сколько реплик было
    до него. Пишем только хвост: перезаписывать всю историю на каждое
    сообщение значит плодить копии одного и того же.
    """
    fresh = messages[already:]
    if not fresh:
        return
    async with sessions() as session:
        for item in fresh:
            content = item.get("content")
            session.add(
                DialogMessage(
                    channel=channel,
                    chat_id=chat_id,
                    role=str(item.get("role") or "user"),
                    content=content if isinstance(content, str) else json.dumps(
                        content, ensure_ascii=False
                    ),
                )
            )
        await session.commit()


async def seen_before(
    sessions: async_sessionmaker[AsyncSession], channel: str, message_id: str
) -> bool:
    """
    Обрабатывали ли уже это сообщение.

    Отметку ставим сразу, а не после ответа. Если упасть посередине, гость
    останется без ответа — неприятно, но поправимо. Обработать дважды хуже:
    он получит два ответа, а то и две брони.
    """
    if not message_id:
        return False
    async with sessions() as session:
        session.add(ChannelReceipt(message_id=message_id, channel=channel))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return True
    return False


async def forget_old(
    sessions: async_sessionmaker[AsyncSession], days: int = 90
) -> int:
    """Убрать давнюю переписку. Держать её вечно незачем и невежливо."""
    edge = hotel_now() - timedelta(days=days)
    async with sessions() as session:
        result = await session.execute(
            delete(DialogMessage).where(DialogMessage.created_at < edge)
        )
        await session.execute(
            delete(ChannelReceipt).where(ChannelReceipt.created_at < edge)
        )
        await session.commit()
        return result.rowcount or 0
