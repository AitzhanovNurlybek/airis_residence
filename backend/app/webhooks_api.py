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

from .booking_system import get_booking_system
from .channels import WhatsAppChannel, WhatsAppError
from .channels.flow import CHANNEL as WA_CHANNEL, Reply, reply_for
from .channels.whatsapp import _parse, for_whatsapp
from .config import Settings, get_settings
from .concierge import FALLBACK
from .db import ExelyEvent, SessionLocal, get_session
from .dialogs import answered_same_recently, save_turn, seen_before

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["вебхуки"])

#: Где искать секрет. Exely называет способ «API-ключ», но имя заголовка в
#: разных установках отличается, а увидеть живой запрос мы пока не могли.
#: Поэтому смотрим во все привычные места; лишнее не мешает, а недостающее
#: означало бы отказ настоящему уведомлению.
SECRET_HEADERS = (
    # В кабинете Exely имя заголовка задаётся вручную, полем «Имя ключа».
    # У нас оно указано как EXELY_WEBHOOK_SECRET — то же самое имя, что и у
    # переменной окружения, но это два разных места: одно в настройках Exely,
    # другое в backend/.env. Заголовки регистронезависимы, но с этим именем
    # его никто раньше не искал: без него настоящее уведомление получало бы
    # 401 при правильном секрете.
    "exely_webhook_secret",
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


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Входящее сообщение из WhatsApp через Green API.

    Второй вход в тот же разговор. `whatsapp_bot.py` опрашивает очередь в
    вечном цикле — это работает, пока включён компьютер. Здесь наоборот:
    Green API сам стучится к нам на Vercel, и консьерж отвечает гостю в три
    часа ночи, когда ноутбук закрыт.

    Включать оба сразу нельзя: Green API отдаёт уведомление либо в вебхук,
    либо в очередь. Если бот опроса тоже запущен, они будут драться за одно
    и то же сообщение.
    """
    secret = (settings.whatsapp_webhook_secret or "").strip()
    if not secret:
        logger.warning("Вебхук WhatsApp пришёл, но WHATSAPP_WEBHOOK_SECRET не задан")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "error": "webhook secret is not configured"}

    if _presented(request) != secret:
        logger.warning("Вебхук WhatsApp с неверным ключом — отброшен")
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"ok": False, "error": "bad key"}

    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        return {"ok": True, "skipped": "не объект"}

    # Green API присылает и исходящие, и статусы доставки, и события групп.
    # _parse отбирает только входящие сообщения от людей и возвращает None
    # для всего остального — на такое отвечаем 200, иначе начнутся повторы.
    message = _parse(payload)
    if message is None or message.is_group:
        return {"ok": True, "skipped": "не входящее сообщение гостя"}
    if not message.text and not message.has_file and not message.is_voice:
        return {"ok": True, "skipped": "пустое сообщение"}

    # Тот же дедуп, что и у опроса: Green API штатно повторяет доставку, если
    # мы ответили медленно. Отметку ставим ДО ответа — остаться без ответа
    # неприятно, но получить два ответа и две брони хуже.
    if await seen_before(SessionLocal, WA_CHANNEL, message.message_id):
        logger.info("Вебхук WhatsApp: повтор %s — пропускаю", message.message_id)
        return {"ok": True, "duplicate": True}

    # Вторая защита, поверх дедупа по идентификатору: WhatsApp при плохой
    # связи доставляет одну фразу гостя как два РАЗНЫХ сообщения, и по
    # идентификатору это не поймать. Гость на этом получал два ответа подряд.
    if message.text and await answered_same_recently(
        SessionLocal, WA_CHANNEL, message.chat_id, message.text
    ):
        logger.info("Вебхук WhatsApp: та же фраза от %s только что — пропускаю",
                    message.phone)
        return {"ok": True, "duplicate": True, "reason": "same text"}

    try:
        channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
    except WhatsAppError as error:
        logger.warning("Вебхук WhatsApp: канал не создан: %s", error)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "error": "green api is not configured"}

    booking = get_booking_system(settings)
    try:
        reply = await reply_for(settings, booking, channel, message)
    except Exception as error:  # noqa: BLE001 — один сбой не должен ронять приём
        logger.exception("Вебхук WhatsApp: обработка упала: %s", error)
        reply = Reply(FALLBACK)

    try:
        await channel.send(message.chat_id, for_whatsapp(reply.text))
    except WhatsAppError as error:
        logger.warning("Вебхук WhatsApp: ответ не ушёл: %s", error)
        return {"ok": False, "error": "send failed"}

    # Снимки идут после текста и по одному. Сбой на картинке не должен
    # выглядеть как сбой ответа: текст гость уже получил, и обрывать
    # обработку из-за неотправленной фотографии — значит превратить мелкую
    # неудачу в молчание.
    sent_photos = 0
    captioned: set[str] = set()
    for photo in reply.photos:
        # Подпись — одна на категорию, у первого снимка. Три одинаковых
        # «Comfort» под тремя фотографиями подряд ничего не добавляют и
        # выглядят как сбой рассылки.
        room = photo.get("room", "")
        caption = "" if room in captioned else room
        captioned.add(room)
        try:
            await channel.send_file(message.chat_id, photo["url"], caption=caption)
            sent_photos += 1
        except WhatsAppError as error:
            logger.warning("Вебхук WhatsApp: снимок не ушёл: %s", error)

    logger.info("Вебхук WhatsApp: ответили %s, снимков %d", message.phone, sent_photos)
    return {"ok": True, "replied": True, "photos": sent_photos}


@router.post("/lifecycle")
async def lifecycle_tick(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Разослать сообщения по ходу брони. Дёргается планировщиком.

    Защита та же, что у остальных вебхуков: без верного секрета точка не
    работает. Адрес открыт интернету, а по нему уходят сообщения гостям от
    имени отеля — запускать это кто угодно не должен.

    `?dry_run=1` показывает, что ушло бы, ничего не отправляя. С этого стоит
    начинать после каждой правки текстов.
    """
    secret = (settings.whatsapp_webhook_secret or "").strip()
    if not secret:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "error": "webhook secret is not configured"}
    if _presented(request) != secret:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"ok": False, "error": "bad key"}

    from .lifecycle import run as lifecycle_run

    dry = request.query_params.get("dry_run") in ("1", "true", "yes")
    result = await lifecycle_run(session, settings, dry_run=dry)
    return {"ok": True, **result}


@router.post("/sync-bookings")
async def sync_bookings(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Перенести порцию броней из Exely — для поиска по имени гостя.

    Дёргается планировщиком. Обрабатывает небольшую пачку за раз и
    продолжает с места, где остановился, поэтому первый полный обход
    занимает несколько запусков, а дальше почти ничего не делает.
    """
    secret = (settings.whatsapp_webhook_secret or "").strip()
    if not secret:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "error": "webhook secret is not configured"}
    if _presented(request) != secret:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"ok": False, "error": "bad key"}

    if not settings.exely_api_ready:
        return {"ok": False, "error": "доступ к API Exely не настроен"}

    from .booking_sync import sync
    from .booking_system.exely_api import ExelyApi

    api = ExelyApi(
        settings.exely_client_id, settings.exely_client_secret,
        settings.exely_property_id, auth_url=settings.exely_auth_url,
        api_base=settings.exely_api_base, timeout=30.0,
    )
    return await sync(session, api, settings.exely_property_id)
