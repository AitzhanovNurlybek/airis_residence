"""
Проверка доступа к официальному API Exely.

Запуск из папки backend, когда интеграторы выдали ключи:

    .\\.venv\\Scripts\\python.exe exely_check.py
    .\\.venv\\Scripts\\python.exe exely_check.py +77015550101   # искать брони по телефону

Зачем отдельный скрипт. Ключи приходят разом, вместе с адресами, и первая
попытка почти никогда не срабатывает с первого раза: то не тот адрес токена,
то propertyId перепутан с кодом отеля 509506. Разбираться в этом через
переписку в WhatsApp — долго. Скрипт проходит цепочку по шагам и на каждом
говорит, что именно не так.

Значения ключей он не печатает никогда — только длину. Один раз ключ уже
утёк в лог через отладочную печать, второй раз не надо.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.booking_system.base import BookingSystemUnavailable  # noqa: E402
from app.booking_system.exely_api import ExelyApi  # noqa: E402
from app.config import get_settings  # noqa: E402

OK = "  ✓ "
NO = "  ✗ "


def mask(value: str) -> str:
    return f"задан, {len(value)} символов" if value else "ПУСТО"


async def main() -> int:
    settings = get_settings()

    print("НАСТРОЙКИ (backend/.env)")
    fields = {
        "EXELY_CLIENT_ID": settings.exely_client_id,
        "EXELY_CLIENT_SECRET": settings.exely_client_secret,
        "EXELY_PROPERTY_ID": settings.exely_property_id,
        "EXELY_AUTH_URL": settings.exely_auth_url,
        "EXELY_API_BASE": settings.exely_api_base,
    }
    for name, value in fields.items():
        # Адреса показываем целиком: они не секрет, а ошибаются в них чаще
        # всего. Ключи — только длиной.
        shown = value if name.endswith("URL") or name.endswith("BASE") else mask(value)
        print(f"{OK if value else NO}{name}: {shown or 'ПУСТО'}")

    missing = [n for n, v in fields.items() if not v]
    if missing:
        print()
        print("Не хватает: " + ", ".join(missing))
        print("Всё это выдают в кабинете Exely:")
        print("  Настройки гостиницы → Подключения API → Создать подключение.")
        print("propertyId — не код отеля 509506. Это разные числа, их легко перепутать.")
        return 1

    if settings.exely_property_id.strip() == settings.exely_hotel_code.strip():
        print()
        print("⚠ EXELY_PROPERTY_ID совпадает с кодом отеля из виджета.")
        print("  Так бывает, но чаще это значит, что скопировали не то число.")

    api = ExelyApi(
        settings.exely_client_id,
        settings.exely_client_secret,
        settings.exely_property_id,
        auth_url=settings.exely_auth_url,
        api_base=settings.exely_api_base,
    )

    print()
    print("ШАГ 1. Токен доступа")
    try:
        token = await api.token()
        print(f"{OK}получен, {len(token)} символов")
    except BookingSystemUnavailable as error:
        print(f"{NO}{error}")
        print("  Чаще всего дело в EXELY_AUTH_URL: адрес токена и адрес API — разные.")
        return 1

    print()
    print("ШАГ 2. Список броней отеля")
    try:
        data = await api._get(f"/v1/properties/{api._property}/bookings")
    except BookingSystemUnavailable as error:
        print(f"{NO}{error}")
        print("  Если ответ 403 — в подключении не отмечен Read Reservation API.")
        print("  Если 404 — неверный propertyId или EXELY_API_BASE.")
        return 1

    rows = api._rows(data)
    print(f"{OK}ответ получен, записей: {len(rows)}")

    if rows and isinstance(rows[0], dict):
        print()
        print("ШАГ 3. Поля в ответе — сверить с разбором в exely_api.py")
        print("  что прислали:", ", ".join(sorted(rows[0].keys()))[:400])
        parsed = api._booking(rows[0])
        if parsed is None:
            print(f"{NO}разобрать не удалось — поля называются иначе, чем мы ждём.")
            print("  Поправь _booking() в app/booking_system/exely_api.py:")
            print("  там перечислены варианты названий, добавь недостающие.")
            return 1
        print(f"{OK}разобралось: {parsed.external_id}, "
              f"{parsed.check_in}—{parsed.check_out}, "
              f"{parsed.total_amount} тг, «{parsed.guest_name}», статус {parsed.status}")
    else:
        print()
        print("  (броней в ответе нет — проверить разбор полей не на чем)")

    phone = sys.argv[1] if len(sys.argv) > 1 else ""
    if phone:
        print()
        print(f"ШАГ 4. Поиск броней по телефону {phone}")
        try:
            found = await api.find_bookings(phone=phone)
        except BookingSystemUnavailable as error:
            print(f"{NO}{error}")
            return 1
        if not found:
            print("  броней по этому номеру нет "
                  "(либо параметр поиска называется иначе — см. find_bookings)")
        for booking in found:
            print(f"{OK}{booking.external_id}: {booking.check_in}—{booking.check_out}, "
                  f"{booking.total_amount} тг, статус {booking.status}")

    print()
    print("Готово. Консьерж увидит брони после перезапуска: BOOKING_SYSTEM=exely.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
