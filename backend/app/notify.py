"""Уведомления о новых заявках."""

import logging

import httpx
from sqlalchemy import select

from .config import get_settings
from .db import Company, CorpBooking, CorpBookingItem, Lead, SessionLocal

logger = logging.getLogger(__name__)

ROOM_NAMES = {
    "standart-single": "Standart Single",
    "standart": "Standart",
    "standart-twin": "Standart Twin",
    "comfort": "Comfort",
    "comfort-plus": "Comfort Plus",
}


def lead_lines(lead: Lead) -> list[str]:
    """Заявка в виде строк. Один текст на все каналы, чтобы не расходились."""
    room = ROOM_NAMES.get(lead.room or "", lead.room or "не выбран")
    lines = [
        f"Заявка с сайта #{lead.id}",
        "",
        f"Имя: {lead.name}",
        f"Телефон: {lead.phone}",
    ]
    if lead.email:
        lines.append(f"Почта: {lead.email}")
    lines += [
        f"Номер: {room}",
        f"Даты: {lead.check_in or '—'} → {lead.check_out or '—'}",
        f"Гостей: {lead.adults or '—'}",
    ]
    if lead.comment:
        lines += ["", f"Комментарий: {lead.comment}"]
    lines += ["", "Перезвоните гостю — он ждёт ответа."]
    return lines


async def notify_whatsapp(lead: Lead) -> None:
    """Шлёт заявку в WhatsApp отеля.

    Заявки уходили только в Telegram, а он у отеля не настроен: шесть штук
    пролежали в базе непрочитанными, у четырёх дата заезда успела пройти.
    Гость заполнял форму и не получал звонка — самая дорогая из возможных
    поломок, и при этом совершенно незаметная.

    WhatsApp выбран потому, что он у отеля уже работает: тот же канал, что и
    у консьержа, те же ключи, ничего настраивать не нужно. По умолчанию
    заявка уходит на номер самого бота — в чат «Сообщение для себя», который
    есть всегда и не зависит от того, кто сегодня на смене.
    """
    settings = get_settings()
    try:
        from .channels.whatsapp import WhatsAppChannel, WhatsAppError, for_whatsapp
        channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
    except Exception as error:  # noqa: BLE001 — канал не настроен, это не сбой заявки
        logger.info("WhatsApp не настроен, заявка #%s только в базе: %s", lead.id, error)
        return

    phone = "".join(ch for ch in (settings.lead_notify_phone or "") if ch.isdigit())
    if not phone:
        # Свой номер узнаём у Green API: в настройках его нет, а зашивать
        # цифрами нельзя — при смене номера отеля заявки уйдут в никуда.
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                answer = await client.get(
                    f"https://api.green-api.com/waInstance{settings.green_api_id}"
                    f"/getSettings/{settings.green_api_token}"
                )
                phone = str((answer.json() or {}).get("wid") or "").split("@")[0]
        except Exception:  # noqa: BLE001
            logger.warning("Не узнать свой номер, заявка #%s не отправлена", lead.id)
            return
    if not phone:
        return

    try:
        await channel.send(f"{phone}@c.us", for_whatsapp("\n".join(lead_lines(lead))))
        logger.info("Заявка #%s ушла в WhatsApp", lead.id)
    except WhatsAppError as error:
        logger.warning("Заявка #%s не ушла в WhatsApp: %s", lead.id, error)


async def notify_hotel_booking(number: str, kind: str) -> None:
    """Сообщить отелю о новой или отменённой брони.

    Заказчица спросила прямо: «оплата прошла, а мне никакое уведомление не
    пришло — как я узнаю?» Никак: платёж проходит между Exely и банком, наша
    система в этой цепочке не участвует и узнать о нём может только от Exely.

    Уведомление о самой броне Exely присылает, и вот его-то мы теперь и
    превращаем в сообщение отелю. Гостю написать по нему нельзя: в брони есть
    имя и фамилия, но нет ни телефона, ни почты — проверено на живой броне.
    А отелю есть что сказать: пришла бронь, вот кто, вот когда, вот на
    сколько.

    Подробности тянем из Exely по номеру: в самом уведомлении лежат только
    номер брони и код объекта.
    """
    settings = get_settings()
    if not number:
        return

    подробности: list[str] = []
    try:
        from .booking_system.exely_api import ExelyApi

        api = ExelyApi(settings.exely_client_id, settings.exely_client_secret,
                       settings.exely_property_id, auth_url=settings.exely_auth_url,
                       api_base=settings.exely_api_base)
        data = await api._get(
            f"/v1/properties/{settings.exely_property_id}/bookings/{number}")
        booking = (data or {}).get("booking") or {}
        who = booking.get("customer") or {}
        имя = " ".join(str(who.get(k) or "").strip()
                       for k in ("lastName", "firstName")).strip()
        stays = booking.get("roomStays") or []
        даты = комната = ""
        if stays and isinstance(stays[0], dict):
            сроки = stays[0].get("stayDates") or {}
            заезд = str(сроки.get("arrivalDateTime") or "")[:10]
            выезд = str(сроки.get("departureDateTime") or "")[:10]
            даты = f"{заезд} → {выезд}" if заезд else ""
            тип = stays[0].get("roomType") or {}
            комната = str(тип.get("name") or "")
        сумма = (booking.get("total") or {}).get("priceAfterTax")

        if имя:
            подробности.append(f"Гость: {имя}")
        if комната:
            подробности.append(f"Номер: {комната}")
        if даты:
            подробности.append(f"Даты: {даты}")
        if сумма:
            # Exely отдаёт сумму дробной («475.0»), а в счёте у отеля тенге
            # целые. Дробная часть тут только мешает читать.
            try:
                округлённая = f"{int(round(float(сумма))):,}".replace(",", " ")
            except (TypeError, ValueError):
                округлённая = str(сумма)
            подробности.append(
                f"Сумма: {округлённая} {booking.get('currencyCode') or ''}".strip())
        статус = str(booking.get("status") or "")
        if статус:
            подробности.append(f"Статус в Exely: {статус}")
    except Exception as error:  # noqa: BLE001 — без подробностей уведомление всё равно нужно
        logger.warning("Подробности брони %s не прочитались: %s", number, error)

    заголовок = ("Новая бронь с сайта" if "cancel" not in kind.lower()
                 else "Бронь отменена")
    lines = [f"{заголовок}: {number}", ""] + подробности
    lines += ["", "Проверить оплату и детали — в кабинете Exely."]

    try:
        from .channels.whatsapp import WhatsAppChannel, WhatsAppError, for_whatsapp
        channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
    except Exception as error:  # noqa: BLE001
        logger.info("WhatsApp не настроен, бронь %s без уведомления: %s", number, error)
        return

    phone = "".join(ch for ch in (settings.lead_notify_phone or "") if ch.isdigit())
    if not phone:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                answer = await client.get(
                    f"https://api.green-api.com/waInstance{settings.green_api_id}"
                    f"/getSettings/{settings.green_api_token}"
                )
                phone = str((answer.json() or {}).get("wid") or "").split("@")[0]
        except Exception:  # noqa: BLE001
            logger.warning("Не узнать свой номер, бронь %s без уведомления", number)
            return
    if not phone:
        return

    try:
        await channel.send(f"{phone}@c.us", for_whatsapp("\n".join(lines)))
        logger.info("Бронь %s (%s) — отель уведомлён", number, kind)
    except WhatsAppError as error:
        logger.warning("Уведомление о брони %s не ушло: %s", number, error)


async def notify_telegram(lead: Lead) -> None:
    """Шлёт заявку в Telegram. Ошибка доставки не должна ронять запрос."""
    settings = get_settings()
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        logger.info("Telegram не настроен, заявка #%s только в базе", lead.id)
        return

    room = ROOM_NAMES.get(lead.room or "", lead.room or "не выбран")
    lines = [
        f"🏨 *Заявка #{lead.id}*",
        "",
        f"👤 {lead.name}",
        f"📞 {lead.phone}",
    ]
    if lead.email:
        lines.append(f"✉️ {lead.email}")
    lines += [
        "",
        f"🛏 Номер: {room}",
        f"📅 {lead.check_in or '—'} → {lead.check_out or '—'}",
        f"👥 Гостей: {lead.adults or '—'}",
    ]
    if lead.comment:
        lines += ["", f"💬 {lead.comment}"]

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": "\n".join(lines),
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error("Telegram вернул %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("Не удалось отправить заявку #%s в Telegram", lead.id)


async def notify_corp_booking(booking_id: int) -> None:
    """
    Шлёт менеджеру заявку из корпоративного кабинета.

    На вход идёт id, а не сама бронь: функция выполняется фоновой задачей уже
    после того, как запрос ответил и его сессия закрылась, — у объекта из той
    сессии здесь отвалились бы все поля. Поэтому читаем заново своей сессией.

    Молчание Telegram тут ничего не теряет: заявка уже лежит в базе и видна в
    админке. Это не тот случай, когда ошибку канала нельзя глушить в лог.
    """
    settings = get_settings()
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        logger.info("Telegram не настроен, бронь #%s только в базе", booking_id)
        return

    async with SessionLocal() as session:
        booking = await session.get(CorpBooking, booking_id)
        if booking is None:
            return
        company = await session.get(Company, booking.company_id)
        items_result = await session.execute(
            select(CorpBookingItem).where(CorpBookingItem.booking_id == booking.id)
        )
        items = list(items_result.scalars().all())

    lines = [
        f"🏢 *Корпоративная заявка {booking.number}*",
        "",
        f"Компания: {company.name if company else '—'}",
        f"📅 {booking.check_in} → {booking.check_out} ({booking.nights} ноч.)",
        f"👥 Гостей: {booking.adults} взр." + (f", {booking.children} дет." if booking.children else ""),
    ]
    if booking.guest_name:
        lines.append(f"👤 Гость: {booking.guest_name}")
    if booking.guest_phone:
        lines.append(f"📞 {booking.guest_phone}")

    lines.append("")
    for item in items:
        lines.append(
            f"🛏 {item.room_name} × {item.rooms_count} — "
            f"{item.price_per_night:,} ₸/ночь".replace(",", " ")
        )
    lines += ["", f"💰 Итого: {booking.total_amount:,} ₸".replace(",", " ")]
    if booking.comment:
        lines += ["", f"💬 {booking.comment}"]

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": "\n".join(lines),
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error("Telegram вернул %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("Не удалось отправить бронь %s в Telegram", booking_id)
