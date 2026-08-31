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

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
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
from .notify import notify_hotel_booking
from .dialogs import answered_same_recently, save_turn, seen_before

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["вебхуки"])

#: Где искать секрет. Exely называет способ «API-ключ», но имя заголовка в
#: разных установках отличается, а увидеть живой запрос мы пока не могли.
#: Поэтому смотрим во все привычные места; лишнее не мешает, а недостающее
#: означало бы отказ настоящему уведомлению.
#: Что ответить на сообщение, содержимое которого мы прочитать не смогли.
#:
#: Гость прислал что-то, чего мы не разбираем: геопозицию, визитку, стикер
#: или тип, которого у мессенджера вчера ещё не было. Раньше такое уходило в
#: тишину, а тишина в переписке читается как «меня игнорируют».
UNREADABLE = (
    "Получили ваше сообщение, но прочитать его содержимое не смог — напишите, "
    "пожалуйста, текстом."
    "\n\n"
    "Подскажу свободные номера и цены на ваши даты, расскажу про отель или найду "
    "вашу бронь."
)

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
    # BookingNumber с большой буквы — так его называет Exely во вложенном
    # payload. Из-за отсутствия этого написания номер не находился ни у
    # одного из 190 уведомлений, накопившихся за месяц.
    for key in ("BookingNumber", "number", "reservationNumber", "bookingNumber", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    for holder in ("payload", "booking", "reservation", "data"):
        nested = payload.get(holder)
        if isinstance(nested, dict):
            found = _number(nested)
            if found:
                return found
    return ""


def _events(body: Any) -> list[dict[str, Any]]:
    """Разложить тело уведомления на отдельные события.

    Exely присылает СПИСОК событий, а не одно:

        [{"eventId": "...", "eventType": "webpms:create_booking",
          "payload": {"BookingNumber": "20260901-...", "PropertyId": "509506"}}]

    Прежний разбор ждал объект и на список отвечал единственной записью с
    типом «unknown» и пустым номером брони. За месяц так накопилось 190
    уведомлений, из которых не извлечено ничего: гости не получили ни
    подтверждений брони, ни сообщений об отмене, а отель не узнал ни об
    одной новой брони с сайта.

    Здесь тело приводится к списку словарей — и одиночный объект, и список,
    и объект со списком внутри. Разбирать по одному событию за раз важно:
    в одном запросе их может прийти несколько, и потерять второе так же
    легко, как раньше терялись все.
    """
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if not isinstance(body, dict):
        return []
    for holder in ("events", "notifications", "items", "data"):
        nested = body.get(holder)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return [body]


def _kind(payload: dict[str, Any], request: Request) -> str:
    for key in ("eventType", "event", "type", "action", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            # Exely называет события «webpms:create_booking». Приставка
            # ничего не различает — все уведомления приходят с ней, — а
            # сопоставление с шаблонами сообщений идёт по «create_booking».
            return value.split(":")[-1][:60] if ":" in value else value[:60]
    # Иные отправители кладут тип события в заголовок, а не в тело.
    return (request.headers.get("x-event-type") or "unknown")[:60]


@router.post("/exely")
async def exely_webhook(
    request: Request,
    response: Response,
    background: BackgroundTasks,
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
    # Одно уведомление может нести несколько событий, и записать надо каждое.
    body = payload if isinstance(payload, (dict, list)) else {"payload": payload}
    events = _events(body) or [{}]

    saved: list[int] = []
    duplicates = 0
    for item in events:
        kind = _kind(item, request)
        number = _number(item)
        phone = _phone(item)

        # Ключ повтора: тип события и номер брони. У Exely на одну бронь
        # приходит и создание, и отмена, поэтому одного номера мало. Номера
        # нет — берём собственный идентификатор события, а его нет — тело
        # целиком, иначе два разных уведомления схлопнутся в одно.
        own = str(item.get("eventId") or "")
        key = f"{kind}:{number}" if number else f"{kind}:{own or hash(raw)}"

        event = ExelyEvent(
            event_key=key[:120],
            kind=kind,
            booking_number=number[:60],
            guest_phone=phone[:40],
            payload=json.dumps(item, ensure_ascii=False)[:20000],
        )
        session.add(event)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            duplicates += 1
            logger.info("Вебхук Exely: повтор события %s", key)
            continue
        saved.append(event.id)
        logger.info("Вебхук Exely: %s по брони %s", kind, number or "без номера")

        # Отель узнаёт о брони отсюда, и только отсюда: платёж проходит между
        # Exely и банком, мимо нас. Отправляем в фоне — уведомление не должно
        # задерживать ответ Exely, иначе он посчитает доставку неудачной и
        # начнёт слать повторы.
        if number and any(w in kind.lower() for w in ("book", "reserv")):
            background.add_task(notify_hotel_booking, number, kind)

    return {"ok": True, "saved": saved, "duplicates": duplicates, "events": len(events)}


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

    # Чат отеля с самим собой. WhatsApp разрешает писать на свой же номер
    # («Сообщение для себя»), и такие заметки приходят обычным входящим.
    # Отвечать на них — значит засорять личный блокнот владельца и, при
    # неудачном стечении, разговаривать с самим собой без конца.
    own = str(payload.get("instanceData", {}).get("wid") or "")
    if own and message.chat_id == own:
        logger.info("Вебхук WhatsApp: заметка отеля самому себе — пропускаю")
        return {"ok": True, "skipped": "сообщение самому себе"}

    if not message.readable:
        # Прочитать не вышло. Молчать можно только там, где молчание —
        # решение: реакция «палец вверх», опрос, правка сообщения. Всё
        # остальное получает ответ, даже если тип нам незнаком.
        #
        # Это правило появилось после двух одинаковых потерь: голосовые и
        # ответы с цитатой уходили в тишину, потому что ветки под них не
        # было, а вебхук честно отчитывался «пустое сообщение». Гость в обоих
        # случаях решил, что отель его не читает.
        if message.is_noise:
            return {"ok": True, "skipped": f"без ответа: {message.kind}"}
        logger.info("Вебхук WhatsApp: не прочитал «%s» от %s", message.kind, message.phone)
        try:
            channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
            await channel.send(message.chat_id, for_whatsapp(UNREADABLE))
        except WhatsAppError as error:
            logger.warning("Вебхук WhatsApp: ответ не ушёл: %s", error)
            return {"ok": False, "error": "send failed"}
        return {"ok": True, "replied": True, "unreadable": message.kind}

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


@router.post("/followup")
async def followup_tick(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Написать тем, чей разговор оборвался на полпути. Дёргается планировщиком.

    Отдельная точка, а не часть рассылки по броням: там поводы календарные и
    хватает двух запусков в день, здесь — тишина в переписке, и проверять её
    нужно часто. Смешав их, пришлось бы либо гонять брони каждый час, либо
    отвечать гостю к вечеру.

    `?dry_run=1` показывает, кому и что ушло бы, ничего не отправляя, и
    работает в любой час — иначе проверить тексты можно было бы только днём.
    """
    secret = (settings.whatsapp_webhook_secret or "").strip()
    if not secret:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "error": "webhook secret is not configured"}
    if _presented(request) != secret:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"ok": False, "error": "bad key"}

    from .followup import run as followup_run

    dry = request.query_params.get("dry_run") in ("1", "true", "yes")
    result = await followup_run(session, settings, dry_run=dry)
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
