"""
Разобрать платёжный документ и свести его с бронью.

    python scan_payment.py путь/к/квитанции.pdf
    python scan_payment.py фото.jpg --no-apply     # только прочитать, не отмечать

Понимает PDF, PNG, JPG и WEBP. Работает с той системой бронирования, которая
включена в .env: при BOOKING_SYSTEM=local — с локальной шахматкой.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.booking_system import get_booking_system  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.payment_docs import describe, match_and_apply, read_document  # noqa: E402


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    auto = "--no-apply" not in sys.argv

    if not args:
        print(__doc__)
        return 2

    path = args[0]
    if not os.path.exists(path):
        print(f"Файла нет: {path}")
        return 1

    settings = Settings()
    if not settings.anthropic_api_key:
        print("Ключ Anthropic не задан в .env")
        return 1

    await init_db()
    booking = get_booking_system(settings)
    if booking is None:
        print("Система бронирования не подключена (BOOKING_SYSTEM в .env пуст)")
        return 1

    with open(path, "rb") as handle:
        data = handle.read()

    print(f"Читаю {os.path.basename(path)} ({len(data) // 1024} КБ) через {booking.name}…\n")
    doc = await read_document(settings, data, os.path.basename(path))
    result = await match_and_apply(booking, doc, auto_apply=auto)

    print(describe(result))

    if result.booking_ref:
        after = await booking.get_booking(result.booking_ref)
        if after is not None:
            print(
                f"\nБронь {after.external_id}: {after.check_in} — {after.check_out}, "
                f"{after.guest_name}, начислено {after.total_amount} ₸"
            )
            invoices = await booking.invoices(external_id=after.external_id)
            for inv in invoices:
                print(f"Счёт {inv.number}: оплачено {inv.paid_amount} из {inv.amount} ₸ ({inv.status})")

    return 0 if result.verdict in ("applied", "review") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
