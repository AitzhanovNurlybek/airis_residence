"""
ИИ-консьерж: правила поведения, инструменты и вызов модели.

Канал (WhatsApp, Instagram, виджет на сайте) сюда не заглядывает — он только
приносит текст и уносит ответ. Так проще: правила разговора живут в одном
месте, и добавление третьего канала не размножает их по копиям.

Главное ограничение, из которого выведено остальное: консьерж говорит от лица
отеля. Всё, что он утверждает про цену, время заезда или наличие мест, гость
воспринимает как обещание. Поэтому:

* факты берутся только из брифа (см. knowledge.py) — модели прямо запрещено
  добирать из общих знаний;
* цену брони считает сервер, а не модель: цифра из разговора никогда не
  попадает в базу;
* чужую бронь нельзя ни увидеть, ни отменить — совпадение телефона проверяется
  до вызова, а не в тексте промпта;
* когда вопрос выходит за бриф — телефон отеля, а не догадка.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from .booking_system import BookingSystem, BookingSystemUnavailable
from .config import Settings
from .knowledge import KnowledgeUnavailable, load_facts, render_brief

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

#: Ответ, когда факты не загрузились. Лучше признаться, чем сочинить цену.
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
- О себе пиши так, чтобы не всплывал род: «проверяю», «нашлась бронь», «готово», а не «проверил» или «нашла». Иначе в одной переписке ты то мужчина, то женщина, и это сразу выдаёт машину.

ЧТО МОЖНО УТВЕРЖДАТЬ
- Только то, что есть в справке ниже. Цены, площади, время заезда, услуги, адрес — строго оттуда.
- Если в справке этого нет — так и скажи и дай телефон отеля. Не угадывай и не считай приблизительно.
- Никогда не придумывай скидки, акции, бонусы и условия отмены, которых нет в справке.

ЧЕГО ТЫ НЕ ЗНАЕШЬ
- Свободен ли номер на конкретные даты — если у тебя нет инструмента проверки наличия.
  Тогда не говори «свободно» и не говори «занято». Говори, что наличие подтвердит стойка, и предложи телефон или бронирование на сайте.
- Ты не принимаешь оплату. Оплата — на стойке или по счёту.
- Про предоплату и штрафы за отмену не рассуждай по памяти. Что об этом известно, приходит из системы бронирования вместе с тарифом; чего там нет — уточняет стойка.

КОГДА ЗВАТЬ ЧЕЛОВЕКА
Сразу передавай на стойку, без попыток решить самому:
- жалоба, конфликт, недовольство уже проживающего гостя;
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

# Что дописать к правилам, когда система бронирования подключена.
LIVE_AVAILABILITY_RULES = """

ПРОВЕРКА НАЛИЧИЯ
У тебя есть инструмент check_availability. Он показывает, сколько номеров каждой категории свободно на весь период.
- Вызывай его, когда гость назвал обе даты. Не угадывай даты за гостя.
- Свободных ноль — так и скажи, и предложи соседние даты или другую категорию.
- Инструмент возвращает тарифы с ценами. Если они пришли — называй цену оттуда, а не из справки: в справке прайс, а продаётся номер по тарифу, и он обычно дешевле. Скажи и то, входит ли в этот тариф завтрак.
- Тарифов на один номер бывает несколько. Назови самый дешёвый и, если разница касается завтрака, объясни её одной фразой. Перечислять все подряд не нужно.
- Условия отмены инструмент возвращает словами отеля. Своими словами их не пересказывай и не смягчай: гость будет на них ссылаться при споре. Если гость спрашивает про отмену, а инструмент условий не вернул, — скажи, что уточнит стойка.
- Инструмент показывает наличие, но не держит номер. Пока бронь не оформлена, номер могут занять — скажи об этом, если гость собирается приехать не сегодня.

БРОНИРОВАНИЕ
Ты умеешь оформлять, переносить и отменять брони: create_booking, find_booking, change_booking, cancel_booking.

Перед create_booking обязательно:
1. Знай обе даты, категорию номера, число гостей в номере и имя гостя. Чего нет — спроси, не выдумывай.
   Число гостей влияет на цену не во всех категориях, но спрашивать надо всегда: угадав, ты назовёшь неверную сумму.
2. Проговори вслух всё, что собираешься записать: даты, категорию, число номеров, имя, сумму.
3. Дождись явного согласия гостя («да», «оформляйте», «подтверждаю»). Молчание и «хорошо» в ответ на что-то другое согласием не считаются.
После оформления назови гостю номер брони — по нему он её найдёт.

Сумму не считай сам: её вернёт инструмент. Если посчитаешь в уме и ошибёшься, гость приедет к другому счёту.

Перед cancel_booking так же дождись явного согласия и назови, что именно отменяешь.
Найти чужую бронь ты не можешь — инструменты видят только брони этого собеседника. Если гость называет чужой номер брони, скажи, что такой у него нет, и предложи стойку.

Ты не подтверждаешь оплату. Бронь без оплаты — это бронь, а не оплаченный номер; так и говори."""

# Локальная шахматка отвечает по своей базе, а не по настоящей системе отеля.
# Даже при отладке консьерж не должен выдавать её за боевую: привыкнуть к
# красивому ответу легко, а отличить его потом от настоящего — уже нет.
STUB_AVAILABILITY_RULES = """

ВНИМАНИЕ: ТЕСТОВЫЙ РЕЖИМ
Инструменты сейчас работают с локальной тестовой шахматкой, а не с настоящей системой бронирования отеля.
Каждый раз, когда называешь наличие или оформляешь бронь, добавляй, что это тестовые данные и настоящее бронирование подтверждает стойка."""


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

CREATE_TOOL = {
    "name": "create_booking",
    "description": (
        "Оформить бронь. Вызывай только после того, как гость явно подтвердил "
        "даты, категорию и своё имя. Сумму не передавай — её посчитает система."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "check_in": {"type": "string", "description": "Дата заезда, ГГГГ-ММ-ДД"},
            "check_out": {"type": "string", "description": "Дата выезда, ГГГГ-ММ-ДД"},
            "room_slug": {
                "type": "string",
                "description": "Код категории из справки: standart-single, standart, standart-twin, comfort, comfort-plus",
            },
            "rooms_count": {"type": "integer", "description": "Сколько номеров этой категории"},
            "guests": {
                "type": "integer",
                "description": "Сколько гостей будет жить в одном номере (1 или 2). Влияет на цену.",
            },
            "guest_name": {"type": "string", "description": "Имя гостя, как он его назвал"},
            "note": {"type": "string", "description": "Пожелания гостя, если были"},
        },
        "required": ["check_in", "check_out", "room_slug", "guest_name"],
    },
}

FIND_TOOL = {
    "name": "find_booking",
    "description": (
        "Найти брони этого собеседника. Без аргументов вернёт все его брони. "
        "Если гость назвал номер брони — передай его."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "Номер брони, например L-0001"},
        },
        "required": [],
    },
}

CHANGE_TOOL = {
    "name": "change_booking",
    "description": "Перенести бронь на другие даты или изменить число номеров.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "Номер брони"},
            "check_in": {"type": "string", "description": "Новая дата заезда, ГГГГ-ММ-ДД"},
            "check_out": {"type": "string", "description": "Новая дата выезда, ГГГГ-ММ-ДД"},
            "rooms_count": {"type": "integer", "description": "Новое число номеров"},
        },
        "required": ["ref"],
    },
}

CANCEL_TOOL = {
    "name": "cancel_booking",
    "description": "Отменить бронь. Вызывай только после явного подтверждения гостя.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "Номер брони"},
            "reason": {"type": "string", "description": "Причина отмены, если гость назвал"},
        },
        "required": ["ref"],
    },
}

#: В каких границах цена из системы бронирования считается настоящей.
#:
#: Отель правит тарифы у себя, и ошибка там мгновенно становится тем, что
#: консьерж говорит гостю. Опечатка в один ноль — 4 000 вместо 40 000 — это
#: обещание, которое отель обязан сдержать: гость покажет переписку.
#:
#: Границы широкие нарочно. Скидка вдвое бывает, скидка в десять раз — нет.
#: Наценка втрое на праздники бывает, в десять раз — нет.
SANE_LOW = 0.4
SANE_HIGH = 3.0


def _sane_price(price: int | None, rack: int | None) -> bool:
    """Похоже ли на настоящую цену, а не на опечатку в кабинете отеля."""
    if not price or price <= 0:
        return False
    if not rack:
        return True  # сравнивать не с чем — верим системе
    return SANE_LOW * rack <= price <= SANE_HIGH * rack


READ_ONLY_TOOLS = [AVAILABILITY_TOOL]
FULL_TOOLS = [AVAILABILITY_TOOL, CREATE_TOOL, FIND_TOOL, CHANGE_TOOL, CANCEL_TOOL]


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


# ─────────────────────────── исполнение инструментов ───────────────────────────


def _parse_date(value: Any) -> date:
    return date.fromisoformat(str(value or "").strip())


def _room_price(facts: dict[str, Any], slug: str, guests: int = 1) -> tuple[str, int] | None:
    """
    Название и цена за ночь для нужного числа гостей.

    Система бронирования отеля считает от числа гостей, а не от номера: в
    Comfort Plus один гость стоит 50 000, а двое — 52 500. Одна цена на номер
    недобирала бы 2 500 за каждую ночь двухместного заезда.
    """
    for room in facts.get("rooms", []):
        if room.get("slug") != slug:
            continue
        single = int(room.get("price") or 0)
        double = int(room.get("priceDouble") or single)
        return room.get("name", slug), (double if guests >= 2 else single)
    return None


def _describe(booking: Any, *, room: str = "") -> str:
    tail = f", {room}" if room else ""
    status = "действует" if booking.status == "booked" else "отменена"
    return (
        f"{booking.external_id}: {booking.check_in} — {booking.check_out}{tail}, "
        f"{booking.guest_name or 'без имени'}, {booking.total_amount} тенге, {status}"
    )


async def _tool_availability(
    booking: BookingSystem, args: dict[str, Any], facts: dict[str, Any] | None = None
) -> str:
    try:
        check_in = _parse_date(args.get("check_in"))
        check_out = _parse_date(args.get("check_out"))
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
        prefix = "ТЕСТОВЫЕ ДАННЫЕ (локальная шахматка, не настоящее наличие).\n"

    lines = []
    for offer in result.offers:
        head = f"- {offer.room_name or offer.room_slug} (код {offer.room_slug}): "
        if not offer.rooms_left:
            lines.append(head + "свободных нет")
            continue
        lines.append(head + f"свободно {offer.rooms_left}")
        rack = None
        if facts:
            priced = _room_price(facts, offer.room_slug)
            rack = priced[1] if priced else None
        # Тарифы, если система их отдаёт. Цена на сайте — прайс, а продаётся
        # номер по тарифу, и он бывает заметно дешевле. Гость, услышавший от
        # консьержа прайс, открывает форму и видит другое число.
        for rate in offer.rates:
            if not _sane_price(rate.price, rack):
                # Цена вне разумных границ — в кабинете отеля явно ошиблись.
                # Гостю такое не показываем: он на неё сошлётся.
                logger.warning(
                    "Подозрительная цена %s на %s при прайсе %s — пропускаю",
                    rate.price, offer.room_slug, rack,
                )
                continue
            about = (
                " с завтраком" if rate.breakfast
                else (" без завтрака" if rate.breakfast is False else "")
            )
            was = f", обычно {rate.was}" if rate.was else ""
            lines.append(f"    · {rate.name}: {rate.price} тенге за ночь{about}{was}")
            if rate.cancellation:
                lines.append(f"      отмена: {rate.cancellation}")

    return (
        f"{prefix}{check_in} — {check_out}, ночей {result.nights}:\n"
        + "\n".join(lines)
    )


async def _tool_create(
    booking: BookingSystem, args: dict[str, Any], facts: dict[str, Any], guest: dict[str, str]
) -> str:
    if not hasattr(booking, "create_booking"):
        return "Эта система бронирования не умеет оформлять брони отсюда."

    try:
        check_in = _parse_date(args.get("check_in"))
        check_out = _parse_date(args.get("check_out"))
    except ValueError:
        return "Даты не разобраны. Нужен формат ГГГГ-ММ-ДД."

    slug = str(args.get("room_slug") or "").strip()
    guests = max(1, int(args.get("guests") or 1))
    priced = _room_price(facts, slug, guests)
    if priced is None:
        codes = ", ".join(r.get("slug", "") for r in facts.get("rooms", []))
        return f"Категории «{slug}» нет. Есть такие: {codes}"

    room_name, price = priced
    rooms_count = max(1, int(args.get("rooms_count") or 1))
    nights = (check_out - check_in).days

    # Сумму считает сервер, а не модель: иначе в базу однажды попадёт цифра из
    # разговора. Считаем по продажному тарифу, если система его отдала, —
    # прайс из справки выше того, по чему гость реально бронирует.
    sold_at = await _live_price(booking, slug, check_in, check_out, rack=price)
    if sold_at:
        price = sold_at
    amount = price * rooms_count * max(nights, 0)

    try:
        created = await booking.create_booking(
            room_slug=slug,
            rooms_count=rooms_count,
            check_in=check_in,
            check_out=check_out,
            guest_name=str(args.get("guest_name") or "").strip(),
            guest_phone=guest.get("phone", ""),
            amount=amount,
            origin="concierge",
            note=str(args.get("note") or "").strip(),
        )
    except Exception as error:  # noqa: BLE001 — текст ошибки уходит модели как есть
        return f"Оформить не удалось: {error}"

    return (
        f"Бронь оформлена. {_describe(created, room=room_name)}. "
        f"Ночей {nights}, гостей в номере {guests}, цена за ночь {price} тенге."
    )


async def _live_price(
    booking: BookingSystem, slug: str, check_in: date, check_out: date,
    rack: int | None = None,
) -> int | None:
    """Самая низкая продажная цена на категорию. None — система молчит."""
    try:
        result = await booking.availability(check_in, check_out)
    except Exception:  # noqa: BLE001 — цена из справки остаётся запасным вариантом
        return None
    offer = next((o for o in result.offers if o.room_slug == slug), None)
    if not offer or not offer.price_per_night:
        return None
    if not _sane_price(offer.price_per_night, rack):
        logger.warning(
            "Не беру цену %s на %s при прайсе %s — считаю по прайсу",
            offer.price_per_night, slug, rack,
        )
        return None
    return offer.price_per_night


async def _tool_find(booking: BookingSystem, args: dict[str, Any], guest: dict[str, str]) -> str:
    if not hasattr(booking, "find_bookings"):
        return "Эта система бронирования не умеет искать брони отсюда."

    phone = guest.get("phone", "")
    if not phone:
        return "Телефон собеседника неизвестен, поэтому найти его брони нельзя. Предложи стойку."

    mine = await booking.find_bookings(phone=phone)
    wanted = str(args.get("ref") or "").strip().upper()
    if wanted:
        # Фильтруем по своим броням, а не ищем по номеру напрямую: иначе
        # достаточно угадать L-0007, чтобы увидеть чужую бронь.
        mine = [b for b in mine if b.external_id == wanted]
        if not mine:
            return f"Брони {wanted} у этого гостя нет."

    if not mine:
        return "У этого гостя броней нет."
    return "\n".join(_describe(b) for b in mine)


async def _tool_change(booking: BookingSystem, args: dict[str, Any], guest: dict[str, str]) -> str:
    if not hasattr(booking, "change_booking"):
        return "Эта система бронирования не умеет менять брони отсюда."

    ref = str(args.get("ref") or "").strip().upper()
    if not await _belongs_to_guest(booking, ref, guest):
        return f"Брони {ref} у этого гостя нет."

    kwargs: dict[str, Any] = {}
    try:
        if args.get("check_in"):
            kwargs["check_in"] = _parse_date(args["check_in"])
        if args.get("check_out"):
            kwargs["check_out"] = _parse_date(args["check_out"])
    except ValueError:
        return "Даты не разобраны. Нужен формат ГГГГ-ММ-ДД."
    if args.get("rooms_count"):
        kwargs["rooms_count"] = int(args["rooms_count"])

    if not kwargs:
        return "Не сказано, что менять: нужны новые даты или число номеров."

    try:
        changed = await booking.change_booking(ref, **kwargs)
    except Exception as error:  # noqa: BLE001
        return f"Изменить не удалось: {error}"
    return f"Бронь изменена. {_describe(changed)}"


async def _tool_cancel(booking: BookingSystem, args: dict[str, Any], guest: dict[str, str]) -> str:
    if not hasattr(booking, "cancel_booking"):
        return "Эта система бронирования не умеет отменять брони отсюда."

    ref = str(args.get("ref") or "").strip().upper()
    if not await _belongs_to_guest(booking, ref, guest):
        return f"Брони {ref} у этого гостя нет."

    try:
        cancelled = await booking.cancel_booking(ref, str(args.get("reason") or "").strip())
    except Exception as error:  # noqa: BLE001
        return f"Отменить не удалось: {error}"
    return f"Бронь отменена. {_describe(cancelled)}"


async def _belongs_to_guest(booking: BookingSystem, ref: str, guest: dict[str, str]) -> bool:
    """
    Проверка «это твоя бронь» до вызова, а не в тексте правил.

    Правило в промпте — просьба, а не запрет: достаточно уговорить модель, и
    она вызовет отмену для чужого номера. Здесь же чужая бронь просто не
    находится, сколько её ни проси.
    """
    phone = guest.get("phone", "")
    if not phone or not ref:
        return False
    mine = await booking.find_bookings(phone=phone)
    return any(b.external_id == ref for b in mine)


# ─────────────────────────────── диалог ───────────────────────────────


async def answer(
    settings: Settings,
    *,
    message: str,
    history: list[dict[str, Any]] | None = None,
    today: str,
    booking: BookingSystem | None = None,
    guest: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Ответ консьержа на одно сообщение.

    `history` — прошлые реплики в формате [{"role": ..., "content": ...}].
    Хранение диалога — забота канала: у WhatsApp и Instagram свои
    идентификаторы собеседника.

    `booking` — система бронирования, если подключена. Без неё консьерж про
    наличие мест не рассуждает вовсе: инструменты не объявляются, и правило
    «наличие подтвердит стойка» остаётся единственным.

    `guest` — кто пишет: {"phone": ..., "name": ...}. Телефон берётся из
    канала, а не из разговора. Именно по нему решается, чьи брони видны:
    сказанному в переписке «это моя бронь L-0007» верить нельзя.
    """
    if not settings.anthropic_api_key:
        return {"text": FALLBACK, "ok": False, "reason": "нет ключа Anthropic"}

    try:
        facts = await load_facts(settings)
    except KnowledgeUnavailable as error:
        return {"text": FALLBACK, "ok": False, "reason": f"нет фактов: {error}"}

    guest = guest or {}
    mode = booking.source if booking else "none"
    system = build_system_prompt(render_brief(facts), today, availability=mode)

    tools: list[dict[str, Any]] = []
    if booking is not None:
        tools = FULL_TOOLS if hasattr(booking, "create_booking") else READ_ONLY_TOOLS

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

    # Пять кругов: хватает на «посмотреть наличие → оформить → назвать номер».
    # Предел нужен на случай, если модель зациклится на уточнении, — в
    # мессенджере это выглядело бы как молчание, а стоило бы денег.
    for _ in range(5):
        payload: dict[str, Any] = {
            "model": settings.concierge_model,
            "max_tokens": settings.concierge_max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                name = block.get("name")
                args = block.get("input") or {}
                tool_calls.append({"name": name, "input": args})

                if name == "check_availability":
                    output = await _tool_availability(booking, args, facts)
                elif name == "create_booking":
                    output = await _tool_create(booking, args, facts, guest)
                elif name == "find_booking":
                    output = await _tool_find(booking, args, guest)
                elif name == "change_booking":
                    output = await _tool_change(booking, args, guest)
                elif name == "cancel_booking":
                    output = await _tool_cancel(booking, args, guest)
                else:
                    output = f"Инструмента {name} нет."

                results.append(
                    {"type": "tool_result", "tool_use_id": block.get("id"), "content": output}
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
            "messages": messages + [{"role": "assistant", "content": text}],
            "usage": {"in": spent_in, "out": spent_out},
        }

    return {"text": FALLBACK, "ok": False, "reason": "модель не сошлась за пять кругов"}
