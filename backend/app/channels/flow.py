"""
Что ответить гостю на одно входящее сообщение.

Вынесено из `whatsapp_bot.py`, потому что теперь у канала два входа, а
поведение должно быть одно.

**Опрос** (`whatsapp_bot.py`) — вечный цикл, спрашивающий Green API «нет ли
чего нового». Работает, пока работает компьютер: закрыл ноутбук — гость
пишет в пустоту.

**Вебхук** (`webhooks_api.py`) — Green API сам стучится к нам на Vercel.
Работает круглосуточно и без единой машины, которую надо не выключать.

Логика ответа при этом одна и та же, и держать её в двух местах нельзя: они
разойдутся на первой же правке, и гость будет получать разные ответы в
зависимости от того, каким путём пришло его сообщение.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from ..almaty import today as hotel_today
from ..concierge import answer
from ..db import SessionLocal
from ..dialogs import load_history, save_turn
from ..knowledge import KnowledgeUnavailable, load_facts
from ..payment_docs import match_and_apply, read_document
from ..guest_messages import VOICE_NOT_SUPPORTED, render
from ..speech import SpeechUnavailable, configured as speech_ready, transcribe
from .whatsapp import Incoming, WhatsAppChannel

log = logging.getLogger("whatsapp")

CHANNEL = "whatsapp"

#: Сколько снимков отправлять за один ответ. Гость просит «фото номера», а не
#: галерею: четыре категории по три снимка — это дюжина картинок подряд, что
#: WhatsApp и сам гость воспримут одинаково плохо.
MAX_PHOTOS = 4


@dataclass
class Reply:
    """Что уходит гостю: текст и, если он просил показать номер, снимки.

    Раньше здесь была просто строка. Но на «покажите фото» текстом ответить
    нечем — нужны файлы, и порядок важен: сначала подпись, потом картинки.
    """

    text: str
    photos: list[dict[str, str]] = field(default_factory=list)

#: Что ответить на присланный файл, который не оказался платёжкой.
NOT_A_RECEIPT = (
    "Получили ваш файл, спасибо. Похоже, это не платёжный документ — передам его "
    "менеджеру, он посмотрит и свяжется с вами."
)

#: И на платёжку, которую нельзя засчитать автоматически.
NEEDS_MANAGER = (
    "Спасибо, платёж получили. Он требует проверки менеджером — он посмотрит "
    "сегодня и подтвердит. Если срочно, позвоните на стойку: +7 (777) 531-00-09."
)


async def handle_text(settings, booking, message: Incoming) -> Reply:
    """Обычная реплика гостя."""
    depth = max(0, settings.concierge_history_depth)
    history = await load_history(SessionLocal, CHANNEL, message.chat_id, depth)

    reply = await answer(
        settings,
        message=message.text,
        history=history,
        today=hotel_today().isoformat(),
        booking=booking,
        # chat_id нужен, чтобы связать имя гостя с этой перепиской: бронь
        # оформляется на сайте, и другого мостика между ней и чатом нет.
        guest={"phone": message.phone, "name": message.sender_name,
               "chat_id": message.chat_id},
    )

    photos = reply.get("photos") or [] if reply["ok"] else []

    if reply["ok"]:
        # В историю кладём то, что модель реально видела: вместе с вызовами
        # инструментов. Без них в следующий раз она не поймёт, откуда взяла
        # числа в собственном прошлом ответе.
        await save_turn(
            SessionLocal, CHANNEL, message.chat_id, reply["messages"], len(history)
        )
    else:
        log.warning("консьерж не ответил: %s", reply.get("reason"))

    return Reply(reply["text"], photos[:MAX_PHOTOS])


async def handle_file(settings, booking, channel: WhatsAppChannel, message: Incoming) -> Reply:
    """Гость прислал файл — скорее всего чек."""
    try:
        data = await channel.download(message.file_url)
    except Exception as error:  # noqa: BLE001
        log.warning("файл не скачался: %s", error)
        return Reply(NEEDS_MANAGER)

    try:
        doc = await read_document(settings, data, message.file_name or "document.pdf")
    except ValueError as error:
        log.info("файл не разобран: %s", error)
        return Reply(NOT_A_RECEIPT)
    except Exception as error:  # noqa: BLE001
        log.warning("разбор файла упал: %s", error)
        return Reply(NEEDS_MANAGER)

    if not doc.is_payment:
        return Reply(NOT_A_RECEIPT)

    try:
        facts = await load_facts(settings)
    except KnowledgeUnavailable:
        facts = None

    result = await match_and_apply(booking, doc, facts=facts)
    log.info("платёжка: %s — %s", result.verdict, result.reason)

    if result.verdict == "applied":
        return Reply(
            f"Оплата получена и записана по брони {result.booking_ref}: "
            f"{result.applied_amount} ₸. Спасибо!"
        )
    if result.verdict == "duplicate":
        return Reply("Этот платёж мы уже получили раньше — всё в порядке, повторно ничего не нужно.")
    if result.verdict == "rejected" and not doc.is_payment:
        return Reply(NOT_A_RECEIPT)
    return Reply(NEEDS_MANAGER)


async def handle_voice(settings, booking, channel: WhatsAppChannel, message: Incoming) -> Reply:
    """Гость записал голосовое.

    Расшифровываем и дальше ведём обычный разговор: для консьержа это
    становится просто репликой гостя, и вся логика — наличие, цены, брони —
    работает как с текстом.

    Если расшифровка не настроена или не удалась, гость получает просьбу
    написать текстом. Молчать нельзя ни при каком сбое: тишина в переписке
    читается как «меня игнорируют», и это хуже любого отказа.
    """
    if speech_ready(settings) and message.file_url:
        try:
            audio = await channel.download(message.file_url)
            spoken = await transcribe(settings, audio, message.file_name or "voice.oga")
        except SpeechUnavailable as error:
            log.warning("голосовое не расшифровано: %s", error)
            spoken = ""
        except Exception as error:  # noqa: BLE001 — сбой не должен ронять ответ
            log.warning("голосовое не скачалось: %s", error)
            spoken = ""

        if spoken:
            # Дальше это обычная реплика. Подменяем текст и идём общим путём,
            # чтобы расшифрованное сохранилось в историю разговора — иначе
            # следующий вопрос гостя повиснет без контекста.
            heard = replace(message, text=spoken)
            log.info("← %s (голосом): %s", message.phone, spoken[:120])
            return await handle_text(settings, booking, heard)

    phone = "+7 (777) 531-00-09"
    try:
        facts = await load_facts(settings)
        phone = facts.get("hotel", {}).get("contacts", {}).get("phonePrimary") or phone
    except KnowledgeUnavailable:
        pass
    return Reply(render(VOICE_NOT_SUPPORTED, phone=phone))


async def reply_for(settings, booking, channel: WhatsAppChannel, message: Incoming) -> Reply:
    """Единая точка: голос, файл или текст — решается здесь, а не в двух местах."""
    if message.is_voice:
        # Проверка стоит первой: голосовое приходит со ссылкой на файл, и без
        # неё оно ушло бы в разбор платёжек, где ему не место.
        return await handle_voice(settings, booking, channel, message)

    if message.has_file:
        return await handle_file(settings, booking, channel, message)
    return await handle_text(settings, booking, message)
