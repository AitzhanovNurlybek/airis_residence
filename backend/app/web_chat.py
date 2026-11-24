"""
Чат на сайте: ИИ-администратор на стойке в «Отель в 3D».

Тот же консьерж, что в WhatsApp (concierge.answer), но для анонимного
посетителя сайта — канал `web`: только безопасные инструменты (номера,
наличие с ценой, ссылка на бронь) и свои правила, см. WEB_CHAT_RULES.

Переписка хранится в той же таблице диалогов под каналом `web`, а не
приходит от браузера: историю, которую прислал клиент, можно подделать —
вписать «ответ администратора» и выдать его модели за сказанное ею.
Фоновые задачи (дожим, сводки) берут только канал whatsapp и сюда не лезут.

Деньги. Ответ стоит ≈ $0.01, а писать может кто угодно, поэтому три предела:
на одного посетителя за визит, на один адрес в сутки и общий в сутки
(WEB_CHAT_DAILY_LIMIT). Сверх предела модель не зовётся. Адрес хранится
только солёным хешем — сам IP в базу не пишем.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select

from . import almaty
from .booking_system import get_booking_system
from .concierge import WEB_CHANNEL, WEB_WHATSAPP, answer
from .config import Settings, get_settings
from . import db as _db
from .db import ChannelReceipt, DialogMessage
from .dialogs import CONTINUES_FOR, _openable, content_of, save_turn
from .throttle import client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/web-chat", tags=["чат на сайте"])

#: Отметки о принятых сообщениях — для подсчёта пределов.
RECEIPTS = "web-chat"
MAX_MESSAGE = 500
PER_VISIT = 30
PER_ADDRESS_DAY = 40
MAX_PHOTOS = 4

LIMIT_TEXT = {
    "visit": "Мы уже долго общаемся 🙂 Чтобы продолжить, напишите нам в WhatsApp "
             f"{WEB_WHATSAPP} — там ответят и администратор, и я.",
    "address": "На сегодня я ответила на все вопросы, что могла. Продолжим в WhatsApp: "
               f"{WEB_WHATSAPP}",
    "day": "Сейчас чат на сайте перегружен. Напишите нам в WhatsApp "
           f"{WEB_WHATSAPP} — ответим быстро.",
    "off": f"Чат на сайте временно закрыт. Напишите нам в WhatsApp {WEB_WHATSAPP}.",
}


class WebChatIn(BaseModel):
    #: Случайный идентификатор визита (crypto.randomUUID в браузере).
    session: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)


def _address_key(request: Request, settings: Settings) -> str:
    соль = settings.secret_key or "airis"
    return hashlib.sha256(f"{соль}|{client_ip(request)}".encode()).hexdigest()[:16]


async def _open_turn(
    address: str, session_id: str, settings: Settings, depth: int
) -> tuple[str, list[dict[str, Any]]]:
    """Пределы, отметка и история — одним соединением.

    База в Сиднее, функции на Vercel — в США: каждый запрос в базу — перелёт
    через океан (~0,25 с). Сначала здесь было три отдельных подсчёта, отметка
    и чтение истории в разных соединениях — 10 перелётов, и ответ в чате шёл
    10 с (замер 2026-11-25). Теперь три предела считаются одним запросом,
    а отметка и история идут в той же сессии.

    Возвращает (исчерпанный предел или '', история для модели).
    """
    if not settings.web_chat_enabled:
        return "off", []
    сейчас = almaty.now()
    сутки = сейчас - timedelta(days=1)
    полночь = сейчас.replace(hour=0, minute=0, second=0, microsecond=0)
    t = ChannelReceipt.created_at
    async with _db.SessionLocal() as db:
        за_день, с_адреса, за_визит = (
            await db.execute(
                select(
                    func.count().filter(t >= полночь),
                    func.count().filter(and_(t >= сутки, ChannelReceipt.message_id.like(f"{address}|%"))),
                    func.count().filter(and_(t >= сутки, ChannelReceipt.message_id.like(f"%|{session_id}|%"))),
                ).where(ChannelReceipt.channel == RECEIPTS, t >= min(полночь, сутки))
            )
        ).one()
        if за_день >= settings.web_chat_daily_limit:
            return "day", []
        if с_адреса >= PER_ADDRESS_DAY:
            return "address", []
        if за_визит >= PER_VISIT:
            return "visit", []

        db.add(ChannelReceipt(message_id=f"{address}|{session_id}|{uuid.uuid4().hex}"[:120],
                              channel=RECEIPTS))
        rows = (
            await db.execute(
                select(DialogMessage)
                .where(
                    DialogMessage.channel == WEB_CHANNEL,
                    DialogMessage.chat_id == session_id,
                    DialogMessage.created_at >= сейчас - CONTINUES_FOR,
                )
                .order_by(DialogMessage.id.desc())
                .limit(max(0, depth))
            )
        ).scalars().all()
        await db.commit()
    history = [{"role": r.role, "content": content_of(r.content)} for r in reversed(rows)]
    return "", _openable(history)


async def _limit(address: str, session_id: str, settings: Settings) -> str:
    """Какой предел исчерпан ('' — никакой). Для проверок: пишет отметку."""
    предел, _ = await _open_turn(address, session_id, settings, 0)
    return предел


def _for_site(text: str) -> str:
    # Ссылки консьержа помечены как пришедшие из WhatsApp — на сайте
    # аналитика должна видеть свой источник.
    return text.replace("utm_source=whatsapp", "utm_source=site_chat")


@router.post("")
async def web_chat(
    data: WebChatIn,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    message = data.message.strip()
    if not message:
        return {"text": "", "ok": False}

    # Server-Timing: в DevTools видно, куда ушли секунды ответа.
    t0 = time.perf_counter()
    фазы: list[str] = []

    def отметить(имя: str) -> None:
        nonlocal t0
        t = time.perf_counter()
        фазы.append(f"{имя};dur={(t - t0) * 1000:.0f}")
        t0 = t

    address = _address_key(request, settings)
    depth = max(0, settings.concierge_history_depth)
    try:
        предел, history = await _open_turn(address, data.session, settings, depth)
    except Exception as error:  # noqa: BLE001 — без базы считать нечем, не рискуем
        logger.warning("Чат на сайте: пределы не посчитаны: %s", error)
        предел, history = "day", []
    отметить("db")
    if предел:
        response.headers["Server-Timing"] = ", ".join(фазы)
        return {"text": LIMIT_TEXT[предел], "ok": False, "limited": True}

    try:
        reply = await answer(
            settings,
            message=message,
            history=history,
            today=almaty.today().isoformat(),
            booking=get_booking_system(settings),
            guest={},
            channel=WEB_CHANNEL,
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Чат на сайте: ответ не собран: %s", error)
        from .concierge import web_cant_answer  # noqa: PLC0415

        return {"text": web_cant_answer(), "ok": False}
    отметить("model")

    if reply.get("ok") and reply.get("messages"):
        try:
            await save_turn(_db.SessionLocal, WEB_CHANNEL, data.session, reply["messages"], len(history))
        except Exception as error:  # noqa: BLE001 — гость ответ получит, история — нет
            logger.warning("Чат на сайте: история не сохранена: %s", error)
    отметить("save")
    response.headers["Server-Timing"] = ", ".join(фазы)

    photos = [
        {"url": p.get("url", ""), "room": p.get("room", "")}
        for p in (reply.get("photos") or [])[:MAX_PHOTOS]
        if str(p.get("url", "")).startswith("http")
    ]
    return {"text": _for_site(reply.get("text") or ""), "ok": bool(reply.get("ok")), "photos": photos}
