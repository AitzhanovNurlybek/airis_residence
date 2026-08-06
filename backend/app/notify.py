"""Уведомления о новых заявках."""

import logging

import httpx

from .config import get_settings
from .db import Lead

logger = logging.getLogger(__name__)

ROOM_NAMES = {
    "standart-single": "Standart Single",
    "standart": "Standart",
    "standart-twin": "Standart Twin",
    "comfort": "Comfort",
    "comfort-plus": "Comfort Plus",
}


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
