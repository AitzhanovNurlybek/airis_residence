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

from app.booking_system import get_booking_system  # noqa: E402
from app.channels import WhatsAppChannel, WhatsAppError  # noqa: E402
from app.channels.flow import CHANNEL, reply_for  # noqa: E402
from app.concierge import FALLBACK  # noqa: E402
from app.dialogs import seen_before  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("whatsapp")

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
            text = await reply_for(settings, booking, channel, message)
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
