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
