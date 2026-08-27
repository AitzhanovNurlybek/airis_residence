"""
Консьерж в WhatsApp.

Запуск (держать открытым, как любой бот):
    python whatsapp_bot.py
    python whatsapp_bot.py --dry-run    # отвечать в консоль, не в WhatsApp

Опрашивает очередь Green API. На каждое сообщение от гостя зовёт того же
консьержа, что отвечает в окне админки, и отправляет ответ обратно.

Что здесь решается, кроме собственно переписки.

**Личность гостя берётся из канала, а не из текста.** Телефон приходит вместе
с сообщением, и именно по нему консьерж видит «свои» брони. Написанному в
переписке «это моя бронь L-0007» верить нельзя.

**Каждое сообщение обрабатывается один раз.** Подтверждение приёма у Green API
иногда не проходит, и то же сообщение приезжает снова. Отметку ставим до
ответа: остаться без ответа неприятно, но получить два ответа и две брони —
хуже.

**Группы пропускаем.** Отель в групповом чате — это не разговор с гостем, а
чужая беседа, куда добавили номер.

**Файлы.** Гость присылает чек — читаем его тем же разбором, что и страница
«Консьерж», и отвечаем по делу. Не платёжку — говорим, что передадим
менеджеру, и не молчим.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.almaty import today as hotel_today  # noqa: E402
from app.booking_system import get_booking_system  # noqa: E402
from app.channels import Incoming, WhatsAppChannel, WhatsAppError  # noqa: E402
from app.concierge import FALLBACK, answer  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.dialogs import load_history, save_turn, seen_before  # noqa: E402
from app.payment_docs import describe, match_and_apply, read_document  # noqa: E402
from app.knowledge import KnowledgeUnavailable, load_facts  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("whatsapp")

CHANNEL = "whatsapp"

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


async def handle_text(settings, booking, message: Incoming) -> str:
    """Обычная реплика гостя."""
    depth = max(0, settings.concierge_history_depth)
    history = await load_history(SessionLocal, CHANNEL, message.chat_id, depth)

    reply = await answer(
        settings,
        message=message.text,
        history=history,
        today=hotel_today().isoformat(),
        booking=booking,
        guest={"phone": message.phone, "name": message.sender_name},
    )

    if reply["ok"]:
        # В историю кладём то, что модель реально видела: вместе с вызовами
        # инструментов. Без них в следующий раз она не поймёт, откуда взяла
        # числа в собственном прошлом ответе.
        await save_turn(
            SessionLocal, CHANNEL, message.chat_id, reply["messages"], len(history)
        )
    else:
        log.warning("консьерж не ответил: %s", reply.get("reason"))

    return reply["text"]


async def handle_file(settings, booking, channel: WhatsAppChannel, message: Incoming) -> str:
    """Гость прислал файл — скорее всего чек."""
    try:
        data = await channel.download(message.file_url)
    except Exception as error:  # noqa: BLE001
        log.warning("файл не скачался: %s", error)
        return NEEDS_MANAGER

    try:
        doc = await read_document(settings, data, message.file_name or "document.pdf")
    except ValueError as error:
        log.info("файл не разобран: %s", error)
        return NOT_A_RECEIPT
    except Exception as error:  # noqa: BLE001
        log.warning("разбор файла упал: %s", error)
        return NEEDS_MANAGER

    if not doc.is_payment:
        return NOT_A_RECEIPT

    try:
        facts = await load_facts(settings)
    except KnowledgeUnavailable:
        facts = None

    result = await match_and_apply(booking, doc, facts=facts)
    log.info("платёжка: %s — %s", result.verdict, result.reason)

    if result.verdict == "applied":
        return (
            f"Оплата получена и записана по брони {result.booking_ref}: "
            f"{result.applied_amount} ₸. Спасибо!"
        )
    if result.verdict == "duplicate":
        return "Этот платёж мы уже получили раньше — всё в порядке, повторно ничего не нужно."
    if result.verdict == "rejected" and not doc.is_payment:
        return NOT_A_RECEIPT
    return NEEDS_MANAGER


async def serve(dry_run: bool = False) -> int:
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("Нет ANTHROPIC_API_KEY в backend/.env — отвечать нечем.")
        return 1

    try:
        channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
    except WhatsAppError as error:
        print(error)
        print("Инстанс заводится на console.green-api.com, там же QR-код.")
        return 1

    state = await channel.state()
    if state != "authorized":
        print(f"Номер не на связи: состояние «{state}».")
        print("Откройте console.green-api.com и отсканируйте QR телефоном отеля.")
        return 1

    await init_db()
    booking = get_booking_system(settings)
    log.info(
        "на связи · система бронирования: %s · ответы: %s",
        getattr(booking, "name", "не подключена"),
        "в консоль" if dry_run else "в WhatsApp",
    )

    while True:
        try:
            receipt, message = await channel.receive(settings.whatsapp_poll_seconds)
        except WhatsAppError as error:
            log.warning("%s — пауза 30 секунд", error)
            await asyncio.sleep(30)
            continue

        if receipt is None:
            continue

        # Подтверждаем всё, что пришло, включая чужое и служебное. Иначе
        # очередь застрянет на первом же уведомлении, которое мы игнорируем.
        # Если Green API не подтвердил удаление — не поднимаем ошибку (сам
        # confirm() её проглатывает), но хотя бы видно в логе, что творится:
        # молчаливый сбой здесь неотличим от шторма повторов на глаз.
        if not await channel.confirm(receipt):
            log.warning("Green API не подтвердил удаление уведомления %s", receipt)

        if message is None or message.is_group:
            continue
        if not message.text and not message.has_file:
            continue

        if await seen_before(SessionLocal, CHANNEL, message.message_id):
            log.info("повтор %s — пропускаю", message.message_id)
            # Пауза, а не мгновенный следующий опрос. Без неё повторная
            # доставка одного и того же сообщения превращается в спин-цикл:
            # receiveNotification не ждёт полный receiveTimeout, если в
            # очереди уже есть что отдать, и без задержки здесь бот долбит
            # API без остановки — увидели это вживую 2026-08-27.
            await asyncio.sleep(3)
            continue

        who = message.sender_name or message.phone
        log.info("← %s: %s", who, (message.text or f"[файл {message.file_name}]")[:120])

        try:
            if message.has_file:
                text = await handle_file(settings, booking, channel, message)
            else:
                text = await handle_text(settings, booking, message)
        except Exception as error:  # noqa: BLE001 — бот не должен падать от одной реплики
            log.exception("ошибка обработки: %s", error)
            text = FALLBACK

        log.info("→ %s: %s", who, text[:120])

        if dry_run:
            continue

        try:
            await channel.send(message.chat_id, text)
        except WhatsAppError as error:
            log.error("не отправилось: %s", error)

        # Пауза против блокировки номера. Мгновенные ответы без остановки —
        # верный способ уехать в бан, особенно на свежем номере.
        await asyncio.sleep(settings.whatsapp_send_delay)


def main() -> int:
    parser = argparse.ArgumentParser(description="Консьерж в WhatsApp")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="отвечать в консоль, ничего не отправляя гостю",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(serve(args.dry_run))
    except KeyboardInterrupt:
        print("\nостановлено")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
