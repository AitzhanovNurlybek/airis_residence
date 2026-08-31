"""
Что стало с платежом: списан, отменён, возвращён.

Вопрос, который задают чаще всех: «страница показала успешную оплату, а
денег на счёте нет — где они?». Ответ почти всегда в статусе самого
платежа, и FreedomPay отдаёт его по API. Ждать ответа менеджера сутки,
чтобы услышать то, что можно спросить за секунду, незачем.

Что покажет статус:

**Авторизация вместо списания.** Деньги на карте заморожены, но со счёта не
ушли и на счёт отеля не поступали. Выглядит как успешная оплата, ею не
являясь.

**Списание.** Деньги ушли, но до расчётного счёта идут по графику выплат —
обычно на следующий рабочий день, а не сразу.

**Возврат.** Отправлен, но до карты добирается днями: это скорость банка
плательщика, и ускорить её нельзя ни с какой стороны.

────────────────────────────────────────────────────────────────────────
ЧТО НУЖНО ДЛЯ ЗАПУСКА

Два значения из кабинета FreedomPay (Настройки → магазин):

    PAYMENT_TERMINAL_ID    номер магазина (pg_merchant_id)
    PAYMENT_CLIENT_SECRET  секретный ключ магазина

Положите их в `backend/.env` — файл вне git, наружу они не уйдут.

    ./.venv/Scripts/python.exe proverka_platezha.py 1841766142
    ./.venv/Scripts/python.exe proverka_platezha.py --order PG1798

Скрипт только спрашивает. Ничего не списывает, не возвращает и не меняет.
"""

from __future__ import annotations

import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.config import get_settings  # noqa: E402
from app.payments import PaymentError, get_provider  # noqa: E402

#: Как переводить статусы на человеческий. Названия приходят от FreedomPay.
СТАТУСЫ = {
    "ok": "успешно",
    "pending": "в обработке",
    "failed": "не прошёл",
    "revoked": "отменён (холд снят)",
    "refunded": "возвращён",
    "partial_refunded": "возвращён частично",
    "captured": "списан",
    "authorized": "авторизован — деньги ЗАМОРОЖЕНЫ, но НЕ списаны",
}

#: Понятные подписи полей. Всё, чего здесь нет, печатается как есть.
ПОДПИСИ = {
    "pg_payment_id": "Номер платежа",
    "pg_order_id": "Номер заказа",
    "pg_transaction_status": "Статус операции",
    "pg_payment_status": "Статус платежа",
    "pg_amount": "Сумма",
    "pg_currency": "Валюта",
    "pg_net_amount": "К зачислению отелю",
    "pg_captured": "Списание проведено",
    "pg_refund_amount": "Возвращено",
    "pg_revoked_amount": "Снято с холда",
    "pg_card_pan": "Карта",
    "pg_card_brand": "Платёжная система",
    "pg_create_date": "Создан",
    "pg_payment_date": "Оплачен",
    "pg_capture_date": "Списан",
    "pg_refund_date": "Возвращён",
    "pg_failure_code": "Код отказа",
    "pg_failure_description": "Причина отказа",
}


async def main() -> int:
    args = [a for a in sys.argv[1:] if a]
    order = ""
    payment = ""
    if "--order" in args:
        order = args[args.index("--order") + 1] if len(args) > args.index("--order") + 1 else ""
    elif args:
        payment = args[0]

    if not order and not payment:
        print(__doc__)
        return 2

    settings = get_settings()
    if not (settings.payment_terminal_id and settings.payment_client_secret):
        print("Нет доступа к FreedomPay.\n")
        print("Впишите в backend/.env два значения из кабинета FreedomPay:")
        print("  PAYMENT_TERMINAL_ID=<номер магазина>")
        print("  PAYMENT_CLIENT_SECRET=<секретный ключ магазина>")
        print("\nОни лежат в кабинете: Настройки → ваш магазин.")
        return 1

    provider = get_provider(settings)
    if not hasattr(provider, "get_status"):
        print(f"Поставщик «{provider.name}» не умеет отвечать про статус.")
        return 1

    try:
        data = await provider.get_status(payment_id=payment, order_id=order)
    except PaymentError as error:
        print(f"FreedomPay не ответил: {error}")
        return 1

    if not data:
        print("Платёж не найден. Проверьте номер.")
        return 1

    print("\n== Что говорит FreedomPay ==\n")
    for key, value in data.items():
        подпись = ПОДПИСИ.get(key, key)
        человечно = СТАТУСЫ.get(str(value).lower())
        print(f"  {подпись:<24} {value}" + (f"  — {человечно}" if человечно else ""))

    # Главный вывод отдельной строкой: ради него всё и запускалось.
    статус = str(data.get("pg_transaction_status") or data.get("pg_payment_status") or "").lower()
    списано = str(data.get("pg_captured") or "").lower() in ("1", "true", "yes")
    возврат = data.get("pg_refund_amount") or data.get("pg_revoked_amount")

    print("\n== Вывод ==\n")
    if возврат and float(str(возврат) or 0) > 0:
        print(f"  Возврат на {возврат} отправлен. До карты он идёт несколько")
        print("  рабочих дней — это скорость банка плательщика, ускорить нельзя.")
    elif статус in ("authorized",) or (статус == "ok" and not списано):
        print("  Это авторизация, а не списание: деньги на карте заморожены,")
        print("  но со счёта не ушли и отелю не поступали. Списание делается")
        print("  отдельным действием, иначе холд снимется сам.")
    elif списано or статус in ("ok", "captured"):
        print("  Списание проведено. На расчётный счёт средства уходят по")
        print("  графику выплат, а не в момент оплаты — сроки в договоре.")
    elif статус in ("pending",):
        print("  Платёж ещё обрабатывается — подождите и проверьте снова.")
    else:
        print(f"  Статус «{статус or 'не назван'}». Расшифровку спросите у поддержки,")
        print("  приложив вывод выше: с ним разбираются за минуту.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
