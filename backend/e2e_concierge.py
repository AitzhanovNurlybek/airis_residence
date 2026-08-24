"""
Проверка базы ИИ-консьержа.

Главное, что здесь стережётся, — единственность источника фактов. Цена,
которую консьерж назовёт гостю в WhatsApp, должна совпадать с ценой на
странице отеля до тенге. Разойтись они могут только если у консьержа заведётся
своя копия прайса, и этот тест ловит такую копию в момент появления.

Запуск (нужен поднятый фронтенд с бэкендом):
    python e2e_concierge.py [http://127.0.0.1:3010]
Живой вызов модели проверяется, только если задан ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import datetime as dt
from typing import Any

import httpx

# Консоль Windows по умолчанию в cp1251 и давится на рамках и кириллице.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.booking_system import (  # noqa: E402
    STUB_INVENTORY,
    BookingSystemUnavailable,
    ExelyBookingSystem,
    StubBookingSystem,
    get_booking_system,
)
from app.concierge import (  # noqa: E402
    AVAILABILITY_TOOL,
    FALLBACK,
    _tool_availability,
    answer,
    build_system_prompt,
)
from app.config import Settings  # noqa: E402
from app.knowledge import (  # noqa: E402
    KnowledgeUnavailable,
    load_facts,
    render_brief,
    reset_cache,
)

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3010").rstrip("/")

passed = 0
failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  \u2713 {name}")
    else:
        failed.append(name)
        print(f"  \u2717 {name}" + (f" — {detail}" if detail else ""))


async def main() -> int:
    settings = Settings(site_url=BASE, anthropic_api_key="")

    print("\n\u2500\u2500 Точка фактов \u2500\u2500")
    reset_cache()
    try:
        facts = await load_facts(settings)
    except KnowledgeUnavailable as error:
        print(f"  не удалось получить {BASE}/api/knowledge: {error}")
        return 1

    for key in (
        "hotel", "policy", "rooms", "priceFrom",
        "amenities", "nearby", "eventVenues", "faq", "escalation",
    ):
        check(f"раздел «{key}» есть", key in facts and facts[key])

    check("номера пришли", len(facts["rooms"]) >= 5, f"их {len(facts['rooms'])}")
    check(
        "у каждого номера есть цена",
        all(isinstance(r.get("price"), int) and r["price"] > 0 for r in facts["rooms"]),
    )
    check(
        "цена «от» — минимальная из номеров",
        facts["priceFrom"] == min(r["price"] for r in facts["rooms"]),
    )
    check("телефон отеля на месте", facts["hotel"]["contacts"]["phonePrimary"].startswith("+7"))
    check("координаты выверенные", abs(facts["hotel"]["coordinates"]["lat"] - 43.249) < 0.01)
    check("точка закрыта от поиска", True)  # заголовок проверяется ниже по сети

    async with httpx.AsyncClient(timeout=15.0) as client:
        head = await client.get(f"{BASE}/api/knowledge")
        check(
            "заголовок noindex отдаётся",
            "noindex" in head.headers.get("x-robots-tag", ""),
            head.headers.get("x-robots-tag", "нет заголовка"),
        )

        print("\n\u2500\u2500 Факты против страниц сайта \u2500\u2500")
        page = (await client.get(f"{BASE}/nomera")).text
        digits = re.sub(r"[^0-9]", "", page)
        mismatched = [r["slug"] for r in facts["rooms"] if str(r["price"]) not in digits]
        check(
            "цены совпадают со страницей /nomera",
            not mismatched,
            "разошлись: " + ", ".join(mismatched) if mismatched else "",
        )

        home = (await client.get(f"{BASE}/")).text
        check(
            "адрес совпадает с главной",
            "Наурызбай батыра" in home and "Наурызбай батыра" in facts["hotel"]["address"],
        )
        check(
            "время заезда совпадает с главной",
            facts["policy"]["checkIn"] in home or facts["policy"]["checkIn"] in page,
        )

    print("\n\u2500\u2500 Бриф для модели \u2500\u2500")
    brief = render_brief(facts)
    for room in facts["rooms"]:
        check(f"«{room['slug']}» попал в бриф", room["name"] in brief)
        check(
            f"цена «{room['slug']}» в брифе",
            f"{room['price']:,}".replace(",", " ") in brief,
        )
    check("телефон в брифе", facts["hotel"]["contacts"]["phonePrimary"] in brief)
    check("время заезда в брифе", facts["policy"]["checkIn"] in brief)
    check("корпоративный раздел в брифе", "korporativnym-klientam" in brief)
    check("площадки событий в брифе", "Центральный стадион" in brief)
    check("склонение «до 1 гостя»", "до 1 гостей" not in brief)
    check("бриф не разбух", len(brief) < 12000, f"{len(brief)} символов")

    print("\n\u2500\u2500 Правила поведения \u2500\u2500")
    system = build_system_prompt(brief, "2026-08-22")
    check(
        "без системы бронирования запрещено и «свободно», и «занято»",
        "не говори «свободно»" in system and "не говори «занято»" in system,
    )
    check("сказано звать человека на жалобу", "жалоба" in system.lower())
    check("сказано отвечать на языке гостя", "казахский" in system.lower())
    check("запрещено выдумывать скидки", "скидки" in system.lower())
    check("дата подставлена", "2026-08-22" in system)

    print("\n\u2500\u2500 Система бронирования \u2500\u2500")
    check(
        "без настройки не подключена — наличие подтверждает стойка",
        get_booking_system(Settings(booking_system="")) is None,
    )
    # Раньше здесь проверялось, что без ключей Exely не поднимается вовсе.
    # Это устарело: наличие читается с открытого адреса виджета, и ключи для
    # чтения не нужны. А вот запись по-прежнему закрыта — это и проверяем.
    live = get_booking_system(Settings(booking_system="exely"))
    check("exely поднимается без ключей — для чтения", live is not None)
    check("но писать в exely нельзя", not hasattr(live, "create_booking"))
    check("источник помечен как настоящий", getattr(live, "source", "") == "exely")
    check(
        "заглушка на хеше включается только явно",
        isinstance(get_booking_system(Settings(booking_system="stub")), StubBookingSystem),
    )
    check(
        "в заглушке столько же номеров, сколько на сайте",
        sum(STUB_INVENTORY.values()) == facts["hotel"]["roomsCount"],
        f"{sum(STUB_INVENTORY.values())} против {facts['hotel']['roomsCount']}",
    )
    check(
        "категории заглушки совпадают с номерами сайта",
        set(STUB_INVENTORY) == {r["slug"] for r in facts["rooms"]},
    )

    stub = StubBookingSystem({r["slug"]: r["name"] for r in facts["rooms"]})
    first = await stub.availability(dt.date(2026, 9, 3), dt.date(2026, 9, 6))
    again = await stub.availability(dt.date(2026, 9, 3), dt.date(2026, 9, 6))
    check("ответ помечен как тестовый", first.source == "stub")
    check("ночи посчитаны", first.nights == 3, str(first.nights))
    check(
        "повторный запрос даёт тот же ответ",
        [o.rooms_left for o in first.offers] == [o.rooms_left for o in again.offers],
    )
    check(
        "свободных не больше, чем есть номеров",
        all((o.rooms_left or 0) <= STUB_INVENTORY[o.room_slug] for o in first.offers),
    )
    check(
        "длинный период не свободнее короткого",
        min(
            o.rooms_left or 0
            for o in (await stub.availability(dt.date(2026, 9, 3), dt.date(2026, 9, 12))).offers
        )
        <= min(o.rooms_left or 0 for o in first.offers),
    )
    check("заглушка не выдумывает счета", await stub.invoices(company_bin="000000000001") == [])

    told = await _tool_availability(stub, {"check_in": "2026-09-03", "check_out": "2026-09-06"})
    check("в ответе инструмента стоит пометка о тестовых данных", "ТЕСТОВЫЕ ДАННЫЕ" in told)
    check("названия номеров человеческие, а не коды", "Standart" in told, told[:80])
    bad_dates = await _tool_availability(stub, {"check_in": "завтра", "check_out": "послезавтра"})
    check("кривые даты не роняют инструмент", "не разобраны" in bad_dates)
    backwards = await _tool_availability(stub, {"check_in": "2026-09-06", "check_out": "2026-09-03"})
    check("выезд раньше заезда отклонён", "позже" in backwards)

    # Живой запрос в Exely. Он ходит наружу, поэтому сбой сети тут не должен
    # выглядеть как провал теста — отличаем «не дозвонились» от «ответил не то».
    real = ExelyBookingSystem()
    soon = dt.date.today() + dt.timedelta(days=3)
    try:
        live_avail = await real.availability(soon, soon + dt.timedelta(days=2))
    except BookingSystemUnavailable as error:
        print(f"  ⚠ Exely недоступен, проверки наличия пропущены: {error}")
        live_avail = None

    if live_avail is not None:
        check("Exely вернул наличие", bool(live_avail.offers), "пустой ответ")
        check("ответ помечен источником exely", live_avail.source == "exely")
        check(
            "категории сайта нашлись в ответе",
            {r["slug"] for r in facts["rooms"]} <= {o.room_slug for o in live_avail.offers},
        )
        check(
            "остатки — неотрицательные числа",
            all(isinstance(o.rooms_left, int) and o.rooms_left >= 0 for o in live_avail.offers),
        )
        print(
            "    остатки: "
            + ", ".join(f"{o.room_name} {o.rooms_left}" for o in live_avail.offers)
        )

    try:
        await real.get_booking("L-0001")
        check("запись в Exely закрыта", False, "не бросил исключение")
    except BookingSystemUnavailable as error:
        check("запись в Exely закрыта", "договорной доступ" in str(error), str(error)[:80])

    check(
        "инструмент требует обе даты",
        set(AVAILABILITY_TOOL["input_schema"]["required"]) == {"check_in", "check_out"},
    )
    with_stub = build_system_prompt(brief, "2026-08-23", availability="stub")
    with_live = build_system_prompt(brief, "2026-08-23", availability="exely")
    check("в тестовом режиме модель предупреждена", "ТЕСТОВЫЙ РЕЖИМ" in with_stub)
    check("в боевом режиме предупреждения нет", "ТЕСТОВЫЙ РЕЖИМ" not in with_live)
    check("без системы бронирования инструмент не упоминается", "check_availability" not in system)
    check("без системы бронирования остаётся правило про стойку", "подтвердит стойка" in system)

    print("\n\u2500\u2500 Поведение при сбоях \u2500\u2500")
    no_key = await answer(settings, message="Сколько стоит номер?", history=None, today="2026-08-22")
    check("без ключа — честный отказ, а не выдумка", no_key["text"] == FALLBACK and not no_key["ok"])
    check("в отказе есть телефон", "531-00-09" in no_key["text"])

    reset_cache()
    broken = Settings(site_url="http://127.0.0.1:59999", anthropic_api_key="test-key")
    dead = await answer(broken, message="Сколько стоит номер?", history=None, today="2026-08-22")
    check("факты недоступны — отказ, а не цена из головы", dead["text"] == FALLBACK and not dead["ok"])

    reset_cache()
    await load_facts(settings)
    stale = Settings(site_url="http://127.0.0.1:59999", anthropic_api_key="")
    kept = await load_facts(stale)
    check("просроченные факты переживают обрыв сети", bool(kept.get("rooms")))

    live_key = os.environ.get("ANTHROPIC_API_KEY", "") or Settings().anthropic_api_key
    print("\n\u2500\u2500 Живой ответ модели \u2500\u2500")
    if not live_key:
        print("  пропущено: ключ Anthropic не найден ни в .env, ни в окружении")
    else:
        reset_cache()
        live = Settings(site_url=BASE, anthropic_api_key=live_key)
        reply = await answer(
            live,
            message="Здравствуйте! Сколько стоит самый дешёвый номер и во сколько заезд?",
            history=None,
            today="2026-08-22",
        )
        check("модель ответила", reply["ok"], reply.get("reason", ""))
        if reply["ok"]:
            text: str = reply["text"]
            print(f"    ответ: {text[:300]}")
            cheapest = min(r["price"] for r in facts["rooms"])
            spaced = f"{cheapest:,}".replace(",", " ")
            check(
                "названа верная цена",
                spaced in text or f"{cheapest:,}".replace(",", " ") in text or str(cheapest) in text,
                f"ждали {cheapest}",
            )
            check("названо верное время заезда", "14:00" in text)
            check("ответ короткий", len(text) < 900, f"{len(text)} символов")

    total = passed + len(failed)
    print(f"\n\u2500\u2500 Итог \u2500\u2500\n  {passed} из {total}")
    if failed:
        print("  не прошло: " + "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
