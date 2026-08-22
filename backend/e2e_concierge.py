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
from typing import Any

import httpx

# Консоль Windows по умолчанию в cp1251 и давится на рамках и кириллице.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.concierge import FALLBACK, answer, build_system_prompt  # noqa: E402
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
    check("модели запрещено угадывать наличие", "шахматка" in system.lower())
    check("сказано звать человека на жалобу", "жалоба" in system.lower())
    check("сказано отвечать на языке гостя", "казахский" in system.lower())
    check("запрещено выдумывать скидки", "скидки" in system.lower())
    check("дата подставлена", "2026-08-22" in system)

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

    live_key = os.environ.get("ANTHROPIC_API_KEY", "")
    print("\n\u2500\u2500 Живой ответ модели \u2500\u2500")
    if not live_key:
        print("  пропущено: ANTHROPIC_API_KEY не задан")
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
            check("названа верная цена", "25 000" in text or "25000" in text)
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
