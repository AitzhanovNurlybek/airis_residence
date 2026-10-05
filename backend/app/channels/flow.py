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
import time
from dataclasses import dataclass, field, replace

from ..almaty import today as hotel_today
from ..concierge import answer
from ..db import SessionLocal
from ..corp_guest import find_corporate
from ..dialogs import guest_texts, last_message_at, load_history, pause_hours, save_turn, seen_before
from ..knowledge import KnowledgeUnavailable, load_facts
from ..payment_docs import match_and_apply, read_document
from ..guest_messages import (
    FILE_RECEIVED,
    FRONT_DESK_PHONE,
    PAYMENT_APPLIED,
    PAYMENT_DUPLICATE,
    PAYMENT_NEEDS_CHECK,
    VOICE_NOT_SUPPORTED,
    guest_language,
    in_language,
)
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

#: Окно, в котором несколько файлов подряд получают один ответ. 2026-10-05
#: гость прислал три снимка брони и получил три одинаковых «Получили ваш
#: файл» подряд — по-русски.
FILE_WINDOW = 600


async def _language(message: Incoming) -> str:
    """Язык гостя для ответов без модели: по подписи, прошлым репликам, номеру."""
    try:
        earlier = await guest_texts(SessionLocal, CHANNEL, message.chat_id)
    except Exception:  # noqa: BLE001 — без истории язык решит номер
        earlier = []
    return guest_language(message.text or "", message.phone, earlier)


async def _hand_to_front_desk(message: Incoming, what: str, *, once: bool = True) -> bool:
    """Передать файл гостя на стойку. False — уже передавали в этом окне.

    Ответ гостю «передали на стойку» — обещание. Раньше его давали, а стойка
    ничего не получала (как и с просьбами гостей до front_desk_request).
    """
    from ..notify import notify_front_desk  # noqa: PLC0415 — notify тянет каналы

    if once and await seen_before(
            SessionLocal, "file-ack", f"{message.chat_id}:{int(time.time() // FILE_WINDOW)}"):
        return False
    try:
        await notify_front_desk(
            request=f"Гость прислал файл в WhatsApp бота: {what}. Посмотрите его в чате и ответьте гостю.",
            guest=message.sender_name or "", phone=message.phone)
    except Exception as error:  # noqa: BLE001 — гостю всё равно ответим
        log.warning("стойка не узнала о файле: %s", error)
    return True


async def handle_text(settings, booking, message: Incoming, *, language: str = "") -> Reply:
    """Обычная реплика гостя.

    `language` — язык гостя, если он уже понятен (снимок: реплика тогда
    служебная, по-русски, и по ней язык не понять).
    """
    depth = max(0, settings.concierge_history_depth)
    history = await load_history(SessionLocal, CHANNEL, message.chat_id, depth)
    # Сколько прошло с прошлой реплики. В самой истории дат нет, и после
    # паузы в несколько дней модель называла цены на прошедшие даты как
    # действующие. Сбой здесь не повод молчать гостю — тогда просто без паузы.
    try:
        пауза = pause_hours(
            await last_message_at(SessionLocal, CHANNEL, message.chat_id))
    except Exception:  # noqa: BLE001
        пауза = None

    # У компании с договором свои цены. Раньше бот про договоры не знал и
    # называл прайс — сотрудник слышал одну цену в переписке и видел другую
    # в кабинете. Поиск только читает справочник и при любом сомнении
    # (телефон у двоих, компания отключена, база молчит) возвращает None.
    корпоратив = await find_corporate(message.phone)

    reply = await answer(
        settings,
        message=message.text,
        history=history,
        today=hotel_today().isoformat(),
        booking=booking,
        # chat_id нужен, чтобы связать имя гостя с этой перепиской: бронь
        # оформляется на сайте, и другого мостика между ней и чатом нет.
        guest={"phone": message.phone, "name": message.sender_name,
               "chat_id": message.chat_id,
               # Сотрудник компании с договором. Узнаётся по телефону —
               # других мостиков нет, гость представляется не всегда.
               # None у обычного гостя, и тогда всё как раньше.
               "corporate": корпоратив,
               # Часы с прошлой реплики. None — разговор первый.
               "pause_hours": пауза,
               "language": language},
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
    """Гость прислал файл — чек, снимок брони, документ.

    Ответ — на языке гостя и один на несколько файлов подряд; всё, что бот
    не засчитал сам, уходит на стойку.
    """
    язык = await _language(message)

    async def _передали(what: str) -> Reply:
        # Второй и третий снимок подряд — без нового ответа: стойка уже знает.
        if not await _hand_to_front_desk(message, what):
            return Reply("")
        return Reply(in_language(FILE_RECEIVED, язык))

    try:
        data = await channel.download(message.file_url)
    except Exception as error:  # noqa: BLE001
        log.warning("файл не скачался: %s", error)
        return await _передали("файл не скачался, бот его не видел")

    try:
        doc = await read_document(settings, data, message.file_name or "document.pdf")
    except ValueError as error:
        log.info("файл не разобран: %s", error)
        return await _передали("бот его не разобрал")
    except Exception as error:  # noqa: BLE001
        log.warning("разбор файла упал: %s", error)
        return await _передали("разобрать не получилось")

    if not doc.is_payment:
        if doc.summary:
            # Снимок прочитан — дальше это обычная реплика: консьерж видит, что
            # на нём, находит бронь, отвечает на языке гостя и помнит снимок в
            # истории. Стойку не дёргаем: бот справляется сам.
            что = "снимок" if (message.file_name or "").lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp")) else "файл"
            пометка = f"[Гость прислал {что}. На нём: {doc.summary}]"
            текст = f"{пометка}\n{message.text}" if message.text else пометка
            return await handle_text(settings, booking, replace(message, text=текст),
                                     language=язык)
        return await _передали("это не платёжный документ")

    try:
        facts = await load_facts(settings)
    except KnowledgeUnavailable:
        facts = None

    result = await match_and_apply(booking, doc, facts=facts)
    log.info("платёжка: %s — %s", result.verdict, result.reason)

    if result.verdict == "applied":
        return Reply(in_language(PAYMENT_APPLIED, язык, ref=result.booking_ref,
                                 amount=result.applied_amount))
    if result.verdict == "duplicate":
        return Reply(in_language(PAYMENT_DUPLICATE, язык))
    # Засчитать сам бот не смог — проверит человек. Раньше гостю обещали
    # «менеджер посмотрит», а менеджер ничего не получал.
    await _hand_to_front_desk(
        message, f"платёжку нужно проверить вручную ({result.reason})", once=False)
    return Reply(in_language(PAYMENT_NEEDS_CHECK, язык, phone=FRONT_DESK_PHONE))


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

    phone = FRONT_DESK_PHONE
    try:
        facts = await load_facts(settings)
        phone = facts.get("hotel", {}).get("contacts", {}).get("phonePrimary") or phone
    except KnowledgeUnavailable:
        pass
    return Reply(in_language(VOICE_NOT_SUPPORTED, await _language(message), phone=phone))


async def reply_for(settings, booking, channel: WhatsAppChannel, message: Incoming) -> Reply:
    """Единая точка: голос, файл или текст — решается здесь, а не в двух местах."""
    if message.is_voice:
        # Проверка стоит первой: голосовое приходит со ссылкой на файл, и без
        # неё оно ушло бы в разбор платёжек, где ему не место.
        return await handle_voice(settings, booking, channel, message)

    if message.has_file:
        return await handle_file(settings, booking, channel, message)
    return await handle_text(settings, booking, message)
