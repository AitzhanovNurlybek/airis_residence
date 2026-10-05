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
Вместо этого — срок давности: реплики старше недели в новый запрос не
подмешиваются, но из базы не исчезают.

Длинная память опасна одним: в истории нет дат, и модель не знает, сколько
прошло. Поэтому вместе с историей берётся время последней реплики, и после
долгой паузы консьерж получает прямое предупреждение — см. `last_message_at`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .almaty import now as hotel_now
from .db import ChannelReceipt, DialogMessage, StaffMessage, utcnow

logger = logging.getLogger(__name__)

#: Сколько ждать продолжения, прежде чем считать разговор прошлым.
#:
#: Трое суток — ровно столько же, сколько дожим считает разговор живым
#: (`followup.MAX_AGE_HOURS`). Раньше здесь были сутки, и сроки разошлись:
#: дожим писал гостье на третий день, она отвечала — а консьерж к тому
#: времени успевал забыть и даты, и категорию, и переспрашивал всё заново.
#: Живой случай 2026-08-30: «Уточню ещё раз: какие даты вас интересуют?» в
#: ответ на реплику по разговору, который сам же и продолжил.
#:
#: Тормошить гостя дольше, чем помнишь его, нельзя. Число реплик при этом
#: ограничено отдельно, так что длиннее память не значит дороже запрос.
#:
#: Неделя — по просьбе отеля (2026-09-13): «бывают разные случаи». Гость
#: спросил в понедельник, вернулся в пятницу — и не должен объяснять всё
#: заново. Дожим при этом по-прежнему пишет только в первые трое суток:
#: помнить дольше можно, тормошить дольше — нет.
CONTINUES_FOR = timedelta(days=7)

#: С какой паузы предупреждать консьержа, что разговор старый.
#:
#: Проверено 2026-09-13: история пятидневной давности, гость спрашивает
#: «а сколько будет стоить?» — и бот 13 сентября называет цену «на 10–11
#: сентября», то есть на прошедшие даты, в 2 случаях из 3. В истории нет дат,
#: модель не знает, что прошли дни. Сутки — граница, после которой названные
#: в разговоре даты, цены и наличие уже нельзя считать действующими.
STALE_AFTER = timedelta(hours=24)


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

    history = [{"role": row.role, "content": content_of(row.content)} for row in reversed(rows)]
    return _openable(history)


def content_of(raw: str) -> Any:
    """Реплика из базы так, как её ждёт модель: строкой или списком блоков.

    Текст гостя лежит как есть, а реплики с инструментами — JSON-списком, и
    различать их приходится при чтении. json.loads здесь коварен: «6359909102»
    (номер брони цифрами), «2» (сколько гостей), «true» — тоже JSON. 2026-10-05
    номер брони Booking.com превратился в число, модель на такую историю
    отвечала 400 «content: Input should be a valid list», и гость до конца
    разговора получал только запасную фразу. Поэтому разобранное принимаем,
    только если вышла строка или список.
    """
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    return parsed if isinstance(parsed, (str, list)) else raw


async def last_message_at(
    sessions: async_sessionmaker[AsyncSession],
    channel: str,
    chat_id: str,
):
    """Когда была последняя реплика в этом чате. None — переписки не было."""
    async with sessions() as session:
        row = (
            await session.execute(
                select(DialogMessage.created_at)
                .where(
                    DialogMessage.channel == channel,
                    DialogMessage.chat_id == chat_id,
                )
                .order_by(DialogMessage.id.desc())
                .limit(1)
            )
        ).scalar()
    return row


def pause_hours(last, now=None) -> float | None:
    """Сколько часов прошло с последней реплики.

    SQLite отдаёт время без часового пояса, Postgres — с ним, и вычитание
    одного из другого падает. Пауза нужна для одного предупреждения, и
    уронить из-за неё ответ гостю нельзя.
    """
    if last is None:
        return None
    from datetime import timezone

    now = now or utcnow()
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return max(0.0, (now - last).total_seconds() / 3600)


def _blocks(message: dict[str, Any], kind: str) -> bool:
    """Есть ли в реплике блоки такого рода."""
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(isinstance(b, dict) and b.get("type") == kind for b in content)


def _openable(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Обрезать историю так, чтобы модель её приняла.

    Окно последних реплик режется по счёту, а вызов инструмента — это ДВЕ
    записи: обращение консьержа (`tool_use`) и пришедший ответ
    (`tool_result`). Граница окна проходит между ними примерно в каждом
    шестом разговоре, и тогда история открывается ответом инструмента, к
    которому нет вопроса. Модель на такое отвечает 400, консьерж — запасным
    текстом, а гость видит «я не смог обработать сообщение».

    Найдено на живом голосовом 2026-08-29: расшифровка сработала, а ответа
    гость не получил — и дело было не в голосе, просто разговор дорос до
    длины, на которой окно разрезало пару. Чем дольше человек переписывается,
    тем вероятнее он это поймает.

    Отсюда два правила. История начинается репликой гостя — и не осиротевшим
    ответом инструмента. История не заканчивается обращением к инструменту
    без ответа: следом модель ждёт результат, а получит новое сообщение
    гостя.
    """
    out = list(history)
    while out and (out[0]["role"] != "user" or _blocks(out[0], "tool_result")):
        out.pop(0)
    while out and out[-1]["role"] == "assistant" and _blocks(out[-1], "tool_use"):
        out.pop()
    return out


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


#: Чем помечено в истории сказанное сотрудником: модель должна понимать, что
#: это ответил человек, а не она сама.
STAFF_MARK = "[Ответил сотрудник отеля] "


async def remember_staff(
    sessions: async_sessionmaker[AsyncSession], channel: str, chat_id: str, text: str,
    *, pauses_bot: bool = True,
) -> None:
    """Сотрудник написал гостю сам: отметить, что в чате человек, и запомнить сказанное."""
    async with sessions() as session:
        session.add(StaffMessage(channel=channel, chat_id=chat_id, text=text,
                                 pauses_bot=pauses_bot))
        session.add(DialogMessage(channel=channel, chat_id=chat_id, role="assistant",
                                  content=STAFF_MARK + text))
        await session.commit()


async def staff_active(
    sessions: async_sessionmaker[AsyncSession], channel: str, chat_id: str, minutes: int
) -> bool:
    """Писал ли сотрудник в этот чат за последние `minutes` минут."""
    if minutes <= 0 or not chat_id:
        return False
    since = utcnow() - timedelta(minutes=minutes)
    async with sessions() as session:
        found = (
            await session.execute(
                select(StaffMessage.id)
                .where(StaffMessage.channel == channel)
                .where(StaffMessage.chat_id == chat_id)
                .where(StaffMessage.pauses_bot.is_(True))
                .where(StaffMessage.created_at >= since)
                .limit(1)
            )
        ).scalar()
    return found is not None


async def guest_wrote_recently(
    sessions: async_sessionmaker[AsyncSession], channel: str, chat_id: str, hours: int = 24
) -> bool:
    """Писал ли гость в этот чат за последние `hours` часов.

    Нужно, чтобы отличить ответ сотрудника в живом разговоре (бот молчит) от
    сообщения, которым сотрудник сам начинает разговор (бот остаётся в чате).
    """
    since = utcnow() - timedelta(hours=hours)
    async with sessions() as session:
        found = (
            await session.execute(
                select(DialogMessage.id)
                .where(DialogMessage.channel == channel)
                .where(DialogMessage.chat_id == chat_id)
                .where(DialogMessage.role == "user")
                .where(DialogMessage.created_at >= since)
                .limit(1)
            )
        ).scalar()
    return found is not None


async def remember_guest(
    sessions: async_sessionmaker[AsyncSession], channel: str, chat_id: str, text: str
) -> None:
    """Реплика гостя, на которую бот не отвечал (в чате был сотрудник), — в историю."""
    if not text:
        return
    async with sessions() as session:
        session.add(DialogMessage(channel=channel, chat_id=chat_id, role="user", content=text))
        await session.commit()


async def guest_texts(
    sessions: async_sessionmaker[AsyncSession], channel: str, chat_id: str, limit: int = 6
) -> list[str]:
    """Последние реплики гостя текстом, от свежих к старым.

    Нужны, чтобы понять язык гостя там, где в самом сообщении букв нет:
    файл, голосовое, номер брони цифрами. Результаты инструментов, которые
    тоже лежат в истории с ролью user, сюда не попадают.
    """
    if not chat_id:
        return []
    async with sessions() as session:
        rows = (
            await session.execute(
                select(DialogMessage.content)
                .where(DialogMessage.channel == channel)
                .where(DialogMessage.chat_id == chat_id)
                .where(DialogMessage.role == "user")
                .order_by(DialogMessage.id.desc())
                .limit(limit * 3)
            )
        ).scalars().all()

    out: list[str] = []
    for raw in rows:
        try:
            content = json.loads(raw)
        except (TypeError, ValueError):
            content = raw
        if isinstance(content, list):
            text = " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            text = str(content or "")
        # Служебные пометки («[Гость прислал снимок…]») пишутся по-русски и
        # язык гостя не показывают.
        if text.strip() and not text.lstrip().startswith("["):
            out.append(text)
        if len(out) >= limit:
            break
    return out


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


async def answered_same_recently(
    sessions: async_sessionmaker[AsyncSession],
    channel: str,
    chat_id: str,
    text: str,
    window_seconds: int = 90,
) -> bool:
    """Отвечали ли только что на точно такое же сообщение из этого чата.

    Вторая защита от двойного ответа, поверх дедупа по idMessage.

    Тот дедуп ловит повтор одного и того же уведомления — и ловит надёжно,
    в логах это видно. Но гость получил два ответа на одну свою фразу, а
    значит WhatsApp доставил её как ДВА разных сообщения с разными
    идентификаторами. Такое бывает при плохой связи, и по идентификатору
    это не поймать: они честно разные.

    Ловим по содержимому: тот же чат, тот же текст, меньше полутора минут
    назад. Живой человек, отправивший одну фразу дважды подряд, не ждёт двух
    одинаковых ответов — так что ложное срабатывание здесь безобидно.
    """
    if not chat_id or not text:
        return False

    since = utcnow() - timedelta(seconds=window_seconds)
    async with sessions() as session:
        rows = (
            await session.execute(
                select(DialogMessage)
                .where(DialogMessage.channel == channel)
                .where(DialogMessage.chat_id == chat_id)
                .where(DialogMessage.created_at >= since)
                .order_by(DialogMessage.id.desc())
                .limit(12)
            )
        ).scalars().all()

    needle = " ".join(text.split()).casefold()
    for row in rows:
        if row.role != "user":
            continue
        body = row.content or ""
        # Реплики гостя хранятся строкой JSON, но текст внутри виден и так —
        # разбирать его ради сравнения незачем.
        if needle and needle in " ".join(body.split()).casefold():
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


#: Сколько ждать своей очереди и когда считать чужую блокировку брошенной.
#: Ответ Opus с инструментами — до ~40 с; брошенная блокировка (функция
#: упала посреди ответа) не должна держать чат дольше пары минут.
TURN_WAIT_SECONDS = 90
TURN_STALE_SECONDS = 150


@asynccontextmanager
async def chat_turn(
    sessions: async_sessionmaker[AsyncSession], channel: str, chat_id: str
) -> AsyncIterator[bool]:
    """Отвечать гостю по очереди: одно сообщение чата — один ответ за раз.

    Гость часто пишет двумя сообщениями подряд: «будем к обеду» — и через
    20 секунд «около 12:00». Каждое приходит отдельным вебхуком, и раньше оба
    ответа собирались параллельно: второй не видел первого и повторял его —
    2026-10-05 гость дважды подряд услышал про ранний заезд за 20 000 ₸ и
    просьбу прислать номер брони.

    Теперь второе сообщение ждёт, пока первое отвечено и записано в историю,
    и отвечается уже с ним перед глазами. Блокировка — строка в той же
    таблице, что и отметки об обработке: уникальный ключ делает её атомарной
    и в Postgres, и в SQLite. Не дождались — отвечаем всё равно: молчание
    хуже повтора. Возвращает, удалось ли занять очередь.
    """
    key = f"lock:{channel}:{chat_id}"[:120]
    deadline = time.monotonic() + TURN_WAIT_SECONDS
    held = False
    while True:
        async with sessions() as session:
            session.add(ChannelReceipt(message_id=key, channel="lock"))
            try:
                await session.commit()
                held = True
                break
            except IntegrityError:
                await session.rollback()
                row = await session.get(ChannelReceipt, key)
                created = row.created_at if row else None
                if created is not None and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if row is None or (created and created < utcnow() - timedelta(seconds=TURN_STALE_SECONDS)):
                    if row is not None:
                        await session.delete(row)
                        await session.commit()
                    continue
        if time.monotonic() > deadline:
            logger.warning("Очередь чата %s не освободилась за %d с — отвечаю без неё",
                           chat_id[-6:], TURN_WAIT_SECONDS)
            break
        await asyncio.sleep(1.5)
    try:
        yield held
    finally:
        if held:
            async with sessions() as session:
                await session.execute(delete(ChannelReceipt).where(ChannelReceipt.message_id == key))
                await session.commit()
