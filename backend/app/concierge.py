"""
ИИ-консьерж: правила поведения и вызов модели.

Канал (WhatsApp, Instagram, виджет на сайте) сюда не заглядывает — он только
приносит текст и уносит ответ. Так проще: правила разговора живут в одном
месте, и добавление третьего канала не размножает их по копиям.

Главное ограничение, из которого выведено остальное: консьерж говорит от лица
отеля. Всё, что он утверждает про цену, время заезда или наличие мест, гость
воспринимает как обещание. Поэтому:

* факты берутся только из брифа (см. knowledge.py) — модели прямо запрещено
  добирать из общих знаний;
* наличие свободных номеров консьерж не знает вообще: шахматка живёт в Exely,
  доступа к ней у нас нет. Обещать «номер свободен» он не имеет права;
* когда вопрос выходит за бриф — телефон отеля, а не догадка.
"""

from __future__ import annotations

from typing import Any

import httpx

from datetime import date

from .booking_system import BookingSystem, BookingSystemUnavailable
from .config import Settings
from .knowledge import KnowledgeUnavailable, load_facts, render_brief

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Ответ, когда факты не загрузились. Лучше признаться, чем сочинить цену.
FALLBACK = (
    "Извините, сейчас не могу свериться с актуальными ценами и наличием. "
    "Позвоните, пожалуйста, на стойку: +7 (777) 531-00-09 — там ответят сразу, круглосуточно."
)

RULES = """Ты — консьерж отеля Airis Residence в Алматы. Ты переписываешься с гостем в мессенджере от лица отеля.

КАК ГОВОРИТЬ
- Коротко. Два-три предложения. Это переписка, а не страница сайта.
- Спокойно и по-человечески, без канцелярита и без восклицаний в каждой строке.
- Отвечай на том языке, на котором написал гость: русский, казахский или английский. Факты ниже даны по-русски — переведи их сам, не заставляй гостя переключаться.
- Никаких «я ИИ» и «как языковая модель». Ты сотрудник отеля. Но если гость прямо спросит, человек ли ты, — не ври: скажи, что ты автоматический помощник отеля и позовёшь сотрудника.

ЧТО МОЖНО УТВЕРЖДАТЬ
- Только то, что есть в справке ниже. Цены, площади, время заезда, услуги, адрес — строго оттуда.
- Если в справке этого нет — так и скажи и дай телефон отеля. Не угадывай и не считай приблизительно.
- Никогда не придумывай скидки, акции, бонусы и условия отмены, которых нет в справке.

ЧЕГО ТЫ НЕ ЗНАЕШЬ
- Свободен ли номер на конкретные даты — если у тебя нет инструмента проверки наличия.
  Тогда не говори «свободно» и не говори «занято». Говори, что наличие подтвердит стойка, и предложи телефон или бронирование на сайте.
- Ты не оформляешь бронь и не принимаешь оплату. Ты доводишь до брони на сайте или до звонка.

КОГДА ЗВАТЬ ЧЕЛОВЕКА
Сразу передавай на стойку, без попыток решить самому:
- жалоба, конфликт, недовольство уже проживающего гостя;
- изменение или отмена уже оформленной брони;
- групповая заявка (от пяти номеров) или мероприятие;
- просьба о цене вне прайса, скидке, особых условиях;
- вопросы по счетам, договорам и документам от юрлица — там отдельный корпоративный раздел.

ЕСЛИ ГОСТЬ ОТ ЮРЛИЦА
У отеля есть корпоративный раздел: договор, цены по договору, счета, кабинет для сотрудников компании.
Дай ссылку из справки и предложи связать с отделом бронирования.

ЧТО ПОЛЕЗНО ПРЕДЛОЖИТЬ САМОМУ
- Если гость приезжает на концерт или матч — скажи, за сколько минут пешком дойти до площадки (это есть в справке).
- Если гость колеблется между номерами — коротко сравни два по цене и площади.
- В конце разговора о заезде — напомни про время заезда и что завтрак включён."""


AVAILABILITY_TOOL = {
    "name": "check_availability",
    "description": (
        "Узнать, сколько номеров каждой категории свободно на указанные даты. "
        "Вызывай, только когда гость назвал обе даты. Если названа одна дата или "
        "период на словах («на выходных»), сначала переспроси."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "check_in": {"type": "string", "description": "Дата заезда, ГГГГ-ММ-ДД"},
            "check_out": {"type": "string", "description": "Дата выезда, ГГГГ-ММ-ДД"},
        },
        "required": ["check_in", "check_out"],
    },
}

# Что дописать к правилам, когда система бронирования подключена.
LIVE_AVAILABILITY_RULES = """

ПРОВЕРКА НАЛИЧИЯ
У тебя есть инструмент check_availability. Он показывает, сколько номеров каждой категории свободно на весь период.
- Вызывай его, когда гость назвал обе даты. Не угадывай даты за гостя.
- Свободных ноль — так и скажи, и предложи соседние даты или другую категорию.
- Инструмент показывает наличие, но не держит номер. Пока бронь не оформлена, номер могут занять — скажи об этом, если гость собирается приехать не сегодня."""

# Заглушка отвечает выдуманными числами. Даже локально консьерж не должен
# выдавать их за настоящие: привыкнуть к красивому ответу легко, а отличить
# его потом от боевого — уже нет.
STUB_AVAILABILITY_RULES = """

ВНИМАНИЕ: ТЕСТОВЫЙ РЕЖИМ
check_availability сейчас отвечает выдуманными числами из локальной заглушки, а не из настоящей системы бронирования.
Каждый раз, когда называешь наличие, добавляй, что это тестовые данные и настоящее наличие подтверждает стойка."""


def build_system_prompt(brief: str, today: str, *, availability: str = "none") -> str:
    rules = RULES
    if availability == "exely":
        rules += LIVE_AVAILABILITY_RULES
    elif availability == "stub":
        rules += LIVE_AVAILABILITY_RULES + STUB_AVAILABILITY_RULES

    return (
        f"{rules}\n\n"
        f"Сегодня {today} (время Алматы).\n\n"
        f"=== СПРАВКА ОБ ОТЕЛЕ (единственный источник фактов) ===\n{brief}"
    )


async def _run_availability(booking: BookingSystem, args: dict[str, Any]) -> str:
    """Ответ инструмента текстом: модель читает его так же, как справку."""
    try:
        check_in = date.fromisoformat(str(args.get("check_in", "")))
        check_out = date.fromisoformat(str(args.get("check_out", "")))
    except ValueError:
        return "Даты не разобраны. Нужен формат ГГГГ-ММ-ДД."

    if check_out <= check_in:
        return "Дата выезда должна быть позже даты заезда."

    try:
        result = await booking.availability(check_in, check_out)
    except BookingSystemUnavailable as error:
        return f"Система бронирования не ответила: {error}"

    if not result.offers:
        return "Система бронирования не вернула ни одной категории."

    prefix = ""
    if result.source == "stub":
        prefix = "ТЕСТОВЫЕ ДАННЫЕ (локальная заглушка, не настоящее наличие).\n"

    rows = "\n".join(
        f"- {offer.room_name or offer.room_slug}: "
        + ("свободных нет" if not offer.rooms_left else f"свободно {offer.rooms_left}")
        for offer in result.offers
    )
    return f"{prefix}{check_in} — {check_out}, ночей {result.nights}:\n{rows}"


async def answer(
    settings: Settings,
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    today: str,
    booking: BookingSystem | None = None,
) -> dict[str, Any]:
    """
    Ответ консьержа на одно сообщение.

    `history` — прошлые реплики в формате [{"role": "user"|"assistant",
    "content": ...}]. Хранение диалога — забота канала: у WhatsApp и Instagram
    свои идентификаторы собеседника, и складывать их в одну таблицу здесь пока
    незачем.

    `booking` — система бронирования, если она подключена. Без неё консьерж
    про наличие мест не рассуждает вовсе: инструмент не объявляется, и правило
    «наличие подтвердит стойка» остаётся единственным.
    """
    if not settings.anthropic_api_key:
        return {"text": FALLBACK, "ok": False, "reason": "нет ключа Anthropic"}

    try:
        facts = await load_facts(settings)
    except KnowledgeUnavailable as error:
        return {"text": FALLBACK, "ok": False, "reason": f"нет фактов: {error}"}

    mode = booking.source if booking else "none"
    system = build_system_prompt(render_brief(facts), today, availability=mode)

    depth = max(0, settings.concierge_history_depth)
    messages: list[dict[str, Any]] = [
        *(history or [])[-depth:],
        {"role": "user", "content": message},
    ]

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    tool_calls: list[dict[str, Any]] = []
    spent_in = 0
    spent_out = 0

    # Больше двух кругов инструменту не нужно: он один и отвечает с первого
    # раза. Предел стоит на случай, если модель зациклится на уточнении дат —
    # в мессенджере это выглядело бы как молчание, а стоило бы денег.
    for _ in range(3):
        payload: dict[str, Any] = {
            "model": settings.concierge_model,
            "max_tokens": settings.concierge_max_tokens,
            "system": system,
            "messages": messages,
        }
        if booking is not None:
            payload["tools"] = [AVAILABILITY_TOOL]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as error:  # noqa: BLE001
            return {"text": FALLBACK, "ok": False, "reason": f"модель недоступна: {error}"}

        usage = data.get("usage", {})
        spent_in += usage.get("input_tokens") or 0
        spent_out += usage.get("output_tokens") or 0
        content = data.get("content", [])

        if data.get("stop_reason") == "tool_use" and booking is not None:
            results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tool_calls.append({"name": block.get("name"), "input": block.get("input")})
                output = await _run_availability(booking, block.get("input") or {})
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.get("id"),
                        "content": output,
                    }
                )
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": results})
            continue

        text = "".join(
            block.get("text", "") for block in content if block.get("type") == "text"
        ).strip()

        if not text:
            return {"text": FALLBACK, "ok": False, "reason": "пустой ответ модели"}

        return {
            "text": text,
            "ok": True,
            "availability": mode,
            "toolCalls": tool_calls,
            "usage": {"in": spent_in, "out": spent_out},
        }

    return {"text": FALLBACK, "ok": False, "reason": "модель не сошлась за три круга"}
