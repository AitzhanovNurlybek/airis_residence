"""
Факты об отеле для ИИ-консьержа.

Консьерж не хранит собственную копию прайса и правил. Он забирает их с
`/api/knowledge` фронтенда, где они собираются из тех же модулей, из которых
сайт рисует страницы, а номера приходят из базы через тот же вызов, что и
страница «Номера».

Так сделано не из чистоты, а по опыту: цены в описаниях номеров однажды уже
разъехались с базой, и их пришлось сверять вручную. У консьержа цена этой
ошибки выше — он называет цифру гостю в личной переписке, и это обещание
отеля, а не строчка на странице.

Отсюда же следует, как вести себя при сбое: если факты не загрузились,
консьерж молчит о ценах и переводит на человека. Ответ «не знаю, вот телефон»
дешевле выдуманной цифры.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .config import Settings

# Кеш на процесс. На Vercel каждая функция живёт своей жизнью, так что это не
# общий кеш на весь сайт, а защита от похода по сети на каждое сообщение
# внутри одного разговора.
_cache: dict[str, Any] = {"data": None, "at": 0.0}


class KnowledgeUnavailable(RuntimeError):
    """Факты не загрузились. Консьерж обязан перевести разговор на человека."""


async def load_facts(settings: Settings, *, force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    fresh = _cache["data"] is not None and now - _cache["at"] < settings.knowledge_ttl_seconds
    if fresh and not force:
        return _cache["data"]

    url = f"{settings.site_url.rstrip('/')}/api/knowledge"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as error:  # noqa: BLE001 — причина сбоя тут не важна
        # Просроченные факты лучше, чем никаких: отель меняет цены редко, а
        # оставить гостя без ответа из-за сетевой икоты — заметный проигрыш.
        if _cache["data"] is not None:
            return _cache["data"]
        raise KnowledgeUnavailable(str(error)) from error

    _cache["data"] = data
    _cache["at"] = now
    return data


def _price(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", " ") + " тенге"
    except (TypeError, ValueError):
        return "цена уточняется"


def _guests(count: Any) -> str:
    """«до 1 гостя», а не «до 1 гостей» — модель повторяет формулировки дословно."""
    try:
        n = int(count)
    except (TypeError, ValueError):
        return "гостей"
    if n % 10 == 1 and n % 100 != 11:
        return "гостя"
    return "гостей"


def render_brief(facts: dict[str, Any]) -> str:
    """
    Факты в виде текста для модели.

    Не JSON: модель одинаково хорошо читает и то и другое, но текст занимает
    заметно меньше токенов, а он уходит в каждый запрос диалога.
    """
    hotel = facts.get("hotel", {})
    policy = facts.get("policy", {})
    contacts = hotel.get("contacts", {})

    lines: list[str] = []
    add = lines.append

    add(f"ОТЕЛЬ: {hotel.get('name')} ({hotel.get('legalName')}), {hotel.get('tagline')}.")
    add(f"Адрес: {hotel.get('address')}. Номеров всего: {hotel.get('roomsCount')}.")
    add(f"Телефон: {contacts.get('phonePrimary')} (и {contacts.get('phoneCity')}).")
    add(f"Почта: {contacts.get('email')}. Стойка: {contacts.get('hours')}.")
    add(f"Сайт: {hotel.get('url')}")

    add("")
    add("ПРАВИЛА:")
    add(f"- Заезд с {policy.get('checkIn')}, выезд до {policy.get('checkOut')}.")
    add(f"- {policy.get('earlyCheckIn')}.")
    add(f"- Дети: {policy.get('children')}.")
    add(f"- С животными: {'можно' if policy.get('pets') else 'нельзя'}.")
    add(f"- Курение в номерах: {'разрешено' if policy.get('smoking') else 'запрещено'}.")
    payment = policy.get("payment") or []
    add(f"- Оплата: {', '.join(payment)}.")

    add("")
    add("НОМЕРА (цена за ночь, завтрак включён):")
    for room in facts.get("rooms", []):
        single = int(room.get("price") or 0)
        double = int(room.get("priceDouble") or single)
        # Цену за двоих пишем, только когда она отличается. Повторять
        # одинаковое число дважды для каждой категории — это лишние токены в
        # каждом сообщении и лишний повод модели запутаться.
        money = _price(single)
        if double and double != single:
            money = f"{_price(single)} за одного, {_price(double)} за двоих"

        extra = ""
        if room.get("extraBedPrice"):
            extra = f" Дополнительное место — {_price(room['extraBedPrice'])}."

        add(
            f"- {room.get('name')} — {money}. "
            f"{room.get('area')}, до {room.get('capacity')} {_guests(room.get('capacity'))}, {room.get('beds')}. "
            f"{room.get('summary')}{extra}"
        )

    add("")
    add("УСЛУГИ: " + "; ".join(f"{a.get('title')} ({a.get('note')})" for a in facts.get("amenities", [])))

    add("")
    add("РЯДОМ: " + "; ".join(
        f"{n.get('name')} — {n.get('distance')}" + (f", {n.get('walk')} пешком" if n.get("walk") else "")
        for n in facts.get("nearby", [])
    ))

    venues = facts.get("eventVenues", [])
    if venues:
        add("")
        add("ПЛОЩАДКИ СОБЫТИЙ РЯДОМ:")
        for venue in venues:
            highlights = "; ".join(venue.get("highlights", []))
            add(f"- {venue.get('name')} ({venue.get('walk')}). {venue.get('note')} {highlights}")

    faq = facts.get("faq", [])
    if faq:
        add("")
        add("ВОПРОСЫ И ОТВЕТЫ С САЙТА:")
        for item in faq:
            add(f"- {item.get('q')} — {item.get('a')}")

    corp = (facts.get("escalation") or {}).get("corporate")
    if corp:
        add("")
        add(f"ЮРЛИЦАМ: договор, счёт и корпоративные цены — {corp}")

    return "\n".join(lines)


def reset_cache() -> None:
    """Сбросить кеш. Нужно тестам и ручному обновлению после правки цен."""
    _cache["data"] = None
    _cache["at"] = 0.0
