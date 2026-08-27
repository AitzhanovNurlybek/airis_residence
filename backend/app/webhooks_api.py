"""
Приём уведомлений от Exely.

Гость оформляет бронь в форме Exely — сами мы её не заводим, такого метода в
их API нет вовсе. Значит узнать о новой брони можно ровно двумя способами:
спрашивать API по кругу или получить уведомление. Второе честнее: консьерж
даёт ссылку на форму, гость её заполняет, и разговор продолжается уже с
номером брони, будто ничего не прерывалось.

Что здесь решается, кроме собственно приёма.

**Адрес открыт всему интернету.** Его узнает любой, кто посмотрит настройки
подключения, и постучаться сможет кто угодно. Поэтому запрос без верного
секрета отбрасывается — иначе в базу отеля пишет улица.

**Повторы приходят штатно.** Если мы ответили медленно или пятисоткой, Exely
пришлёт то же уведомление снова. Второй раз событие не заводится: ключ
уникален.

**Отвечаем 200 почти всегда.** Отправитель на ошибку начинает слать повторы,
а разобрать неожиданное тело мы можем и потом — оно сохранено целиком.
Отказываем только тем, кто не прошёл проверку секрета.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .db import ExelyEvent, get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["вебхуки"])

#: Где искать секрет. Exely называет способ «API-ключ», но имя заголовка в
#: разных установках отличается, а увидеть живой запрос мы пока не могли.
#: Поэтому смотрим во все привычные места; лишнее не мешает, а недостающее
#: означало бы отказ настоящему уведомлению.
SECRET_HEADERS = (
    "x-api-key",
    "x-webhook-key",
    "x-exely-key",
    "x-exely-signature",
    "api-key",
    "authorization",
)


def _presented(request: Request) -> str:
    """Секрет, который принёс запрос."""
    for name in SECRET_HEADERS:
        value = request.headers.get(name)
        if value:
            # «Bearer abc» и «abc» — одно и то же для наших целей.
            return value.split(None, 1)[-1].strip()
    return (request.query_params.get("key") or "").strip()


def _phone(payload: dict[str, Any]) -> str:
    """Телефон гостя из тела уведомления, где бы он ни лежал."""
    for key in ("phone", "phoneNumber", "contactPhone"):
        value = payload.get(key)
        if value:
            return str(value)
    for key in ("guest", "customer", "mainGuest"):
        guest = payload.get(key)
        if isinstance(guest, dict):
            for inner in ("phone", "phoneNumber", "contactPhone"):
                if guest.get(inner):
                    return str(guest[inner])
    guests = payload.get("guests")
    if isinstance(guests, list):
        for guest in guests:
            if isinstance(guest, dict):
                for inner in ("phone", "phoneNumber", "contactPhone"):
                    if guest.get(inner):
                        return str(guest[inner])
    return ""


def _number(payload: dict[str, Any]) -> str:
    for key in ("number", "reservationNumber", "bookingNumber", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    booking = payload.get("booking") or payload.get("reservation")
    if isinstance(booking, dict):
        return _number(booking)
    return ""


def _kind(payload: dict[str, Any], request: Request) -> str:
    for key in ("eventType", "event", "type", "action", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value[:60]
    # Иные отправители кладут тип события в заголовок, а не в тело.
    return (request.headers.get("x-event-type") or "unknown")[:60]


@router.post("/exely")
async def exely_webhook(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Уведомление о создании или отмене брони."""
    secret = (settings.exely_webhook_secret or "").strip()
    if not secret:
        # Без настроенного секрета точка не работает вовсе. Открытая запись в
        # базу отеля — не то, что стоит включать «пока по-быстрому».
        logger.warning("Вебхук Exely пришёл, но EXELY_WEBHOOK_SECRET не задан")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "error": "webhook secret is not configured"}

    if _presented(request) != secret:
        logger.warning("Вебхук Exely с неверным ключом — отброшен")
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"ok": False, "error": "bad key"}

    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        # Тело сохраняем даже нечитаемое: разбираться проще по факту, чем по
        # строчке в логе «пришло что-то не то».
        payload = {}
    if not isinstance(payload, dict):
        payload = {"payload": payload}

    kind = _kind(payload, request)
    number = _number(payload)
    phone = _phone(payload)

    # Ключ повтора: тип события и номер брони. Номера нет — берём тело
    # целиком, иначе два разных уведомления схлопнутся в одно.
    key = f"{kind}:{number}" if number else f"{kind}:{hash(raw)}"

    event = ExelyEvent(
        event_key=key[:120],
        kind=kind,
        booking_number=number[:60],
        guest_phone=phone[:40],
        payload=(raw or b"").decode("utf-8", "replace")[:20000],
    )
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = (
            await session.execute(select(ExelyEvent).where(ExelyEvent.event_key == key[:120]))
        ).scalar_one_or_none()
        logger.info("Вебхук Exely: повтор события %s", key)
        return {"ok": True, "duplicate": True, "id": existing.id if existing else None}

    logger.info("Вебхук Exely: %s по брони %s", kind, number or "без номера")
    return {"ok": True, "id": event.id, "kind": kind, "booking": number}
