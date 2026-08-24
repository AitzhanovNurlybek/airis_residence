"""
Общий QA-прогон: всё, что можно проверить без обращения к модели.

Дополняет живые прогоны, а не заменяет их. Здесь то, что должно ломаться
громко и мгновенно: разбор чужих ответов, границы дат, права доступа, режимы
работы. Модель сюда не зовут — эти проверки должны идти секунды и не стоить
денег, чтобы их гоняли перед каждым выпуском, а не раз в неделю.

Запуск (фронтенд на 3000 нужен только для разделов про справку):
    python e2e_qa.py [http://127.0.0.1:3000]
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx  # noqa: E402

from app.almaty import HOTEL_TZ, days_until  # noqa: E402
from app.almaty import today as hotel_today  # noqa: E402
from app.booking_system import (  # noqa: E402
    BookingSystemUnavailable,
    ExelyBookingSystem,
    HybridBookingSystem,
    LocalBookingSystem,
    StubBookingSystem,
    get_booking_system,
)
from app.booking_system.exely import ROOM_TYPES  # noqa: E402
from app.concierge import (  # noqa: E402
    FULL_TOOLS,
    _sane_price,
    READ_ONLY_TOOLS,
    build_system_prompt,
    _tool_availability,
    _tool_cancel,
    _tool_find,
)
from app.channels.whatsapp import Incoming, _parse, _phone, for_whatsapp  # noqa: E402
from app.config import Settings  # noqa: E402
from app.dialogs import load_history, save_turn, seen_before  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.knowledge import render_brief  # noqa: E402
from app.payment_docs import (  # noqa: E402
    PaymentDoc,
    _date_problem,
    _words_disagree,
    _words_to_number,
    check_recipient,
    match_and_apply,
)

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000").rstrip("/")

passed = 0
failed: list[str] = []
section = ""


def head(title: str) -> None:
    global section
    section = title
    print(f"\n── {title} ──")


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed.append(f"{section}: {name}")
        print(f"  ✗ {name}" + (f" — {detail}" if detail else ""))


# ─────────────────────────── время отеля ───────────────────────────


def qa_time() -> None:
    head("Время отеля")

    check("пояс отеля — плюс пять", hotel_today() is not None)
    for utc_hour, same_day in ((12, True), (18, True), (19, False), (23, False)):
        moment = datetime(2026, 8, 24, utc_hour, 30, tzinfo=timezone.utc)
        local = moment.astimezone(HOTEL_TZ)
        check(
            f"UTC {utc_hour}:30 → Алматы {local:%d.%m %H:%M}",
            (moment.date() == local.date()) is same_day,
            f"сервер {moment.date()}, отель {local.date()}",
        )

    check("сегодня по отелю не в прошлом", days_until(hotel_today()) == 0)
    check("завтра — это один день", days_until(hotel_today() + timedelta(days=1)) == 1)
    check("вчера — минус один", days_until(hotel_today() - timedelta(days=1)) == -1)

    # Главное: бизнес-логика больше не зовёт date.today() напрямую.
    import pathlib
    import re

    root = pathlib.Path(__file__).parent / "app"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "almaty.py":
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.split("\n"), 1):
            if re.search(r"\bdate\.today\(\)", line) and "hotel_today" not in line:
                offenders.append(f"{path.name}:{number}")
    check(
        "нигде не осталось date.today() в обход времени отеля",
        not offenders,
        ", ".join(offenders),
    )


# ──────────────────────── разбор ответа Exely ────────────────────────


def qa_exely_parsing() -> None:
    head("Разбор ответа Exely")

    exely = ExelyBookingSystem()

    empty = exely._offers({"room_stays": [], "room_type_quotas": []})
    check("пустой ответ — всё занято, а не пусто", len(empty) == len(ROOM_TYPES))
    check("в пустом ответе везде ноль", all(o.rooms_left == 0 for o in empty))

    quoted = exely._offers(
        {
            "room_stays": [
                {"room_types": [{"code": "5050496", "room_type_quota_rph": "111"}]},
                {"room_types": [{"code": "5050496", "room_type_quota_rph": "111"}]},
            ],
            "room_type_quotas": [{"rph": "111", "quantity": 3}],
        }
    )
    comfort = next(o for o in quoted if o.room_slug == "comfort")
    check("одна категория из двух вариантов не удваивается", comfort.rooms_left == 3,
          str(comfort.rooms_left))

    fallback = exely._offers(
        {
            "room_stays": [{"room_types": [{"code": "5050493", "limited_inventory_count": 2}]}],
            "room_type_quotas": [],
        }
    )
    standart = next(o for o in fallback if o.room_slug == "standart")
    check("без квоты берётся признак дефицита", standart.rooms_left == 2, str(standart.rooms_left))

    unknown = exely._offers(
        {
            "room_stays": [{"room_types": [{"code": "9999999", "room_type_quota_rph": "1"}]}],
            "room_type_quotas": [{"rph": "1", "quantity": 5}],
        }
    )
    check("незнакомая категория не показывается гостю",
          all(o.room_slug in ROOM_TYPES.values() for o in unknown))

    nothing_known = exely._offers(
        {
            "room_stays": [{"room_types": [{"code": "5050495"}]}],
            "room_type_quotas": [],
        }
    )
    plus = next(o for o in nothing_known if o.room_slug == "comfort-plus")
    check("продаётся, но количество неизвестно — считаем что есть", plus.rooms_left >= 1,
          str(plus.rooms_left))

    check("коды категорий не потерялись", len(ROOM_TYPES) == 6, str(len(ROOM_TYPES)))
    check("Apart известен", "apart" in ROOM_TYPES.values())

    # Тарифы: по ним консьерж называет цену, поэтому разбор проверяем отдельно.
    from app.booking_system.exely import RATE_PLANS

    priced = exely._offers(
        {
            "room_stays": [
                {
                    "rate_plans": [{"code": "10139493"}],
                    "room_types": [
                        {
                            "code": "5050496",
                            "room_type_quota_rph": "7",
                            "placements": [
                                {"price_after_tax": 41000.0,
                                 "discount": {"basic_after_tax": 45000.0}}
                            ],
                        }
                    ],
                },
                {
                    "rate_plans": [{"code": "10123672"}],
                    "room_types": [
                        {
                            "code": "5050496",
                            "room_type_quota_rph": "7",
                            "placements": [{"price_after_tax": 40500.0}],
                        }
                    ],
                },
            ],
            "room_type_quotas": [{"rph": "7", "quantity": 3}],
        }
    )
    comfort_priced = next(o for o in priced if o.room_slug == "comfort")
    check("тарифы разобраны", len(comfort_priced.rates) == 2, str(len(comfort_priced.rates)))
    check("цена — самая низкая из тарифов", comfort_priced.price_per_night == 40500,
          str(comfort_priced.price_per_night))
    check("тарифы отсортированы по цене",
          [r.price for r in comfort_priced.rates] == [40500, 41000])
    no_breakfast = next(r for r in comfort_priced.rates if r.price == 41000)
    check("«без завтрака» распознан", no_breakfast.breakfast is False)
    check("старая цена сохранена", no_breakfast.was == 45000, str(no_breakfast.was))
    weekend = next(r for r in comfort_priced.rates if r.price == 40500)
    check("«выходные» — с завтраком", weekend.breakfast is True)
    check("без скидки старой цены нет", weekend.was is None)

    unnamed = exely._offers(
        {
            "room_stays": [
                {
                    "rate_plans": [{"code": "999", "name": "Новый тариф без завтрака"}],
                    "room_types": [
                        {"code": "5050493", "room_type_quota_rph": "1",
                         "placements": [{"price_after_tax": 39000.0}]},
                    ],
                }
            ],
            "room_type_quotas": [{"rph": "1", "quantity": 2}],
        }
    )
    fresh = next(o for o in unnamed if o.room_slug == "standart").rates[0]
    check("незнакомый тариф разобран по названию", fresh.breakfast is False, str(fresh.breakfast))

    mystery = exely._offers(
        {
            "room_stays": [
                {
                    "rate_plans": [{"code": "888", "name": "Спецпредложение"}],
                    "room_types": [
                        {"code": "5050493", "room_type_quota_rph": "1",
                         "placements": [{"price_after_tax": 39000.0}]},
                    ],
                }
            ],
            "room_type_quotas": [{"rph": "1", "quantity": 2}],
        }
    )
    vague = next(o for o in mystery if o.room_slug == "standart").rates[0]
    check("про завтрак непонятно — не выдумываем", vague.breakfast is None, str(vague.breakfast))
    check("известные тарифы отеля описаны", len(RATE_PLANS) == 3, str(len(RATE_PLANS)))


# ───────────────────── режимы системы бронирования ─────────────────────


def qa_modes() -> None:
    head("Режимы системы бронирования")

    cases = {
        "": (None, None),
        "hybrid": (HybridBookingSystem, True),
        "exely": (ExelyBookingSystem, False),
        "local": (LocalBookingSystem, True),
        "stub": (StubBookingSystem, False),
    }
    for mode, (klass, writes) in cases.items():
        system = get_booking_system(Settings(booking_system=mode))
        if klass is None:
            check(f"«{mode or 'пусто'}» — системы нет", system is None)
            continue
        check(f"«{mode}» поднимает {klass.__name__}", isinstance(system, klass),
              type(system).__name__)
        check(f"«{mode}» умеет писать: {writes}", hasattr(system, "create_booking") is writes)

    check("опечатка в настройке не поднимает ничего наугад",
          get_booking_system(Settings(booking_system="exeli")) is None)

    hybrid = get_booking_system(Settings(booking_system="hybrid"))
    check("гибрид помечен настоящим источником", hybrid.source == "exely")
    local = get_booking_system(Settings(booking_system="local"))
    check("учебная шахматка помечена тестовой", local.source == "stub")


# ─────────────────────── инструменты консьержа ───────────────────────


def qa_tools() -> None:
    head("Инструменты консьержа")

    names = {t["name"] for t in FULL_TOOLS}
    check("полный набор — пять инструментов", len(FULL_TOOLS) == 5, str(len(FULL_TOOLS)))
    check("есть проверка наличия", "check_availability" in names)
    check("есть оформление", "create_booking" in names)
    check("только чтение — один инструмент", len(READ_ONLY_TOOLS) == 1)
    check("в режиме чтения оформления нет",
          "create_booking" not in {t["name"] for t in READ_ONLY_TOOLS})

    for tool in FULL_TOOLS:
        schema = tool["input_schema"]
        check(f"«{tool['name']}» описан по-человечески", len(tool["description"]) > 40)
        check(f"«{tool['name']}» имеет схему", schema.get("type") == "object")

    create = next(t for t in FULL_TOOLS if t["name"] == "create_booking")
    check("оформление спрашивает число гостей", "guests" in create["input_schema"]["properties"])
    check("сумму модель не передаёт", "amount" not in create["input_schema"]["properties"])

    # Отель правит тарифы у себя, и опечатка там мгновенно становится тем, что
    # консьерж скажет гостю. Границы широкие: скидка вдвое бывает, в десять — нет.
    for price, rack, ok, why in (
        (40500, 45000, True, "обычная акция"),
        (22500, 45000, True, "скидка вдвое"),
        (4000, 40000, False, "потерян ноль"),
        (150000, 45000, False, "лишний ноль"),
        (0, 45000, False, "ноль"),
        (40500, None, True, "прайса нет — верим системе"),
    ):
        check(f"цена {price} при прайсе {rack}: {why}", _sane_price(price, rack) is ok)

    brief = "СПРАВКА"
    none_mode = build_system_prompt(brief, "2026-08-24", availability="none")
    stub_mode = build_system_prompt(brief, "2026-08-24", availability="stub")
    live_mode = build_system_prompt(brief, "2026-08-24", availability="exely")
    check("без системы — правило про стойку", "подтвердит стойка" in none_mode)
    check("без системы инструментов не обещаем", "check_availability" not in none_mode)
    check("в тестовом режиме есть предупреждение", "ТЕСТОВЫЙ РЕЖИМ" in stub_mode)
    check("в боевом предупреждения нет", "ТЕСТОВЫЙ РЕЖИМ" not in live_mode)
    check("везде запрещено выдумывать скидки", all("скидки" in m for m in (none_mode, live_mode)))
    check("везде сказано про язык гостя", all("казахский" in m for m in (none_mode, live_mode)))


# ───────────────────────── проверка платёжек ─────────────────────────


def qa_payments() -> None:
    head("Разбор платёжек")

    for text, want in (
        ("сто тысяч тенге 00 тиын", 100000),
        ("сорок пять тысяч", 45000),
        ("двести пятьдесят тысяч тенге", 250000),
        ("один миллион тенге", 1000000),
        ("девяносто тысяч", 90000),
        ("", None),
        ("абракадабра", None),
    ):
        check(f"пропись «{text or 'пусто'}» → {want}", _words_to_number(text) == want,
              str(_words_to_number(text)))

    agree = PaymentDoc(amount=100000, amount_in_words="сто тысяч тенге")
    disagree = PaymentDoc(amount=90000, amount_in_words="сорок пять тысяч тенге")
    unreadable = PaymentDoc(amount=90000, amount_in_words="девяносто тыщ")
    check("совпавшая пропись молчит", not _words_disagree(agree))
    check("расхождение прописи ловится", bool(_words_disagree(disagree)))
    check("неразобранная пропись не обвиняет", not _words_disagree(unreadable))

    check("дата в будущем ловится",
          bool(_date_problem(PaymentDoc(paid_at=(hotel_today() + timedelta(days=3)).isoformat()))))
    check("сегодняшняя дата проходит",
          not _date_problem(PaymentDoc(paid_at=hotel_today().isoformat())))
    check("вчерашняя проходит",
          not _date_problem(PaymentDoc(paid_at=(hotel_today() - timedelta(days=1)).isoformat())))
    check("годовалая ловится",
          bool(_date_problem(PaymentDoc(paid_at=(hotel_today() - timedelta(days=400)).isoformat()))))
    check("кривая дата не роняет", not _date_problem(PaymentDoc(paid_at="вчера")))

    facts = {"hotel": {"legalName": 'ТОО "INCOME HOUSE"', "legal": {
        "bin": "200640012670", "iik": "KZ8596503F0013625797KZT"}}}
    ours = PaymentDoc(payee="ТОО INCOME HOUSE", payee_bin="200640012670")
    alien = PaymentDoc(payee="ТОО ДРУГОЙ ОТЕЛЬ", payee_bin="111111111111")
    blank = PaymentDoc()
    by_name = PaymentDoc(payee="INCOME HOUSE TOO")
    check("свой БИН узнаётся", check_recipient(ours, facts)[0] == "ok")
    check("чужой БИН отвергается", check_recipient(alien, facts)[0] == "mismatch")
    check("без получателя — «не знаю», а не «чужой»", check_recipient(blank, facts)[0] == "unknown")
    check("узнаётся по названию", check_recipient(by_name, facts)[0] == "ok")
    check("без реквизитов отеля не обвиняем", check_recipient(alien, None)[0] != "ok")


# ─────────────────────── гибрид: наличие и заявки ───────────────────────


async def qa_hybrid() -> None:
    head("Гибрид: наличие настоящее, брони заявками")

    await init_db()
    hybrid = HybridBookingSystem(SessionLocal, {"comfort": "Comfort"})

    check_in = hotel_today() + timedelta(days=2)
    check_out = check_in + timedelta(days=2)

    try:
        free = await hybrid.availability(check_in, check_out)
    except BookingSystemUnavailable as error:
        print(f"  ⚠ Exely недоступен, раздел пропущен: {error}")
        return

    check("наличие пришло", bool(free.offers))
    check("источник — настоящий", free.source == "exely")
    have = {o.room_slug: (o.rooms_left or 0) for o in free.offers}
    available = next((slug for slug, n in have.items() if n > 0), None)
    busy = next((slug for slug, n in have.items() if n == 0), None)
    print(f"    остатки: {have}")

    if busy:
        try:
            await hybrid.create_booking(
                room_slug=busy, rooms_count=1, check_in=check_in, check_out=check_out,
                guest_name="QA", guest_phone="+7 700 000 99 99")
            check("на занятую категорию заявка не проходит", False, "прошла")
        except ValueError as error:
            check("на занятую категорию заявка не проходит", "занят" in str(error).lower(),
                  str(error))

    if not available:
        print("  ⚠ свободных категорий нет — запись не проверить")
        return

    made = await hybrid.create_booking(
        room_slug=available, rooms_count=1, check_in=check_in, check_out=check_out,
        guest_name=QA_LEAD, guest_phone="+7 700 000 99 99", amount=90000)
    check("заявка создана", made.external_id.startswith("Z-"), made.external_id)
    check("заявка действует", made.status == "booked")

    for written in ("+7 700 000 99 99", "87000009999", "7000009999"):
        found = await hybrid.find_bookings(phone=written)
        check(f"находится по номеру «{written}»",
              any(b.external_id == made.external_id for b in found))

    stranger = await hybrid.find_bookings(phone="+7 705 111 22 33")
    check("чужая заявка не находится",
          not any(b.external_id == made.external_id for b in stranger))
    check("без телефона ничего не находится", not await hybrid.find_bookings(phone=""))

    moved = await hybrid.change_booking(
        made.external_id, check_in=check_in + timedelta(days=1),
        check_out=check_out + timedelta(days=1))
    check("перенос заявки работает", moved.check_in == check_in + timedelta(days=1))

    try:
        await hybrid.change_booking(made.external_id, check_in=check_out, check_out=check_in)
        check("перевёрнутые даты отвергаются", False, "прошли")
    except ValueError:
        check("перевёрнутые даты отвергаются", True)

    off = await hybrid.cancel_booking(made.external_id, "проверка")
    check("отмена работает", off.status == "cancelled")

    missing = await hybrid.get_booking("Z-999999")
    check("несуществующая заявка не выдумывается", missing is None)
    check("чужой формат номера не ломает", await hybrid.get_booking("мусор") is None)

    from sqlalchemy import delete as sql_delete

    from app.db import Lead

    async with SessionLocal() as session:
        await session.execute(sql_delete(Lead).where(Lead.name == QA_LEAD))
        await session.commit()


# ──────────────────── права доступа в инструментах ────────────────────


async def qa_access() -> None:
    head("Права: чужое не отдаём")

    system = LocalBookingSystem(SessionLocal, {"comfort": "Comfort"})
    check_in = hotel_today() + timedelta(days=5)
    mine = await system.create_booking(
        room_slug="comfort", rooms_count=1, check_in=check_in,
        check_out=check_in + timedelta(days=1),
        guest_name=QA_GUEST, guest_phone="+7 701 555 44 33")

    owner = {"phone": "+7 701 555 44 33"}
    stranger = {"phone": "+7 702 000 00 00"}
    nobody: dict[str, str] = {}

    seen = await _tool_find(system, {}, owner)
    check("свою бронь видно", mine.external_id in seen, seen[:80])

    hidden = await _tool_find(system, {"ref": mine.external_id}, stranger)
    check("чужую по номеру не отдаёт", mine.external_id not in hidden or "нет" in hidden.lower(),
          hidden[:80])

    anon = await _tool_find(system, {}, nobody)
    check("без телефона ничего не показывает", "неизвест" in anon.lower(), anon[:80])

    refused = await _tool_cancel(system, {"ref": mine.external_id}, stranger)
    still = await system.get_booking(mine.external_id)
    check("чужую отменить нельзя", still is not None and still.status == "booked", refused[:80])

    ghost = await _tool_cancel(system, {"ref": "L-999999"}, owner)
    check("несуществующую отменить нельзя", "нет" in ghost.lower(), ghost[:80])

    bad_dates = await _tool_availability(system, {"check_in": "вчера", "check_out": "завтра"})
    check("кривые даты в инструменте не роняют", "не разобраны" in bad_dates)
    reversed_dates = await _tool_availability(
        system, {"check_in": "2026-09-10", "check_out": "2026-09-08"})
    check("выезд раньше заезда отвергается", "позже" in reversed_dates)

    # Отмена оставляет строку в списке, и после десятка прогонов песочница
    # состоит из «Владелец брони». Прогон должен убирать за собой полностью.
    await _wipe(QA_GUEST)


#: Имя, под которым прогон заводит свои брони. По нему же их и убирает:
#: телефон в базе лежит как ввели, с пробелами, и поиск по цифрам мимо.
QA_GUEST = "Владелец брони (QA)"
#: То же для заявок гибридного режима.
QA_LEAD = "Гость прогона (QA)"


async def _wipe(guest_name: str) -> None:
    from sqlalchemy import delete as sql_delete

    from app.db import LocalBooking

    async with SessionLocal() as session:
        await session.execute(
            sql_delete(LocalBooking).where(LocalBooking.guest_name == guest_name)
        )
        await session.commit()


# ─────────────────────── справка и цены на сайте ───────────────────────


async def qa_channels() -> None:
    head("Канал WhatsApp")

    check("телефон из chatId", _phone("77015550011@c.us") == "+77015550011")
    check("групповой чат распознан", Incoming("1", "123@g.us", "", "", "т").is_group)
    check("личный чат не групповой", not Incoming("1", "123@c.us", "", "", "т").is_group)

    text_in = _parse({
        "typeWebhook": "incomingMessageReceived",
        "idMessage": "ABC123",
        "senderData": {"chatId": "77015550011@c.us", "senderName": "Айгуль"},
        "messageData": {"typeMessage": "textMessage",
                        "textMessageData": {"textMessage": "  Есть номера?  "}},
    })
    check("текстовое разобрано", text_in is not None and text_in.text == "Есть номера?")
    check("имя отправителя взято", text_in.sender_name == "Айгуль")
    check("телефон подставлен", text_in.phone == "+77015550011")

    quoted = _parse({
        "typeWebhook": "incomingMessageReceived",
        "idMessage": "D1",
        "senderData": {"chatId": "77015550011@c.us"},
        "messageData": {"typeMessage": "extendedTextMessage",
                        "extendedTextMessageData": {"text": "а на выходные?"}},
    })
    check("ответ на сообщение разобран", quoted is not None and quoted.text == "а на выходные?")

    doc_in = _parse({
        "typeWebhook": "incomingMessageReceived",
        "idMessage": "F1",
        "senderData": {"chatId": "77015550011@c.us"},
        "messageData": {"typeMessage": "documentMessage",
                        "fileMessageData": {"downloadUrl": "https://x/f.pdf",
                                            "fileName": "чек.pdf", "caption": "оплатил"}},
    })
    check("файл разобран", doc_in is not None and doc_in.has_file)
    check("имя файла взято", doc_in.file_name == "чек.pdf")
    check("подпись к файлу не потеряна", doc_in.text == "оплатил")

    check("исходящее игнорируется", _parse({"typeWebhook": "outgoingMessageStatus"}) is None)
    check("служебное игнорируется", _parse({"typeWebhook": "outgoingAPIMessageReceived"}) is None)
    check("пустое тело не роняет", _parse({}) is None)

    tidy = for_whatsapp("## Цены" + chr(10) + chr(10) + "**Comfort** — 40 500" + chr(10) + "- завтрак")
    check("заголовки убраны", "#" not in tidy, tidy)
    check("жирный по-вотсаповски", "*Comfort*" in tidy, tidy)
    check("список точками", "•" in tidy, tidy)

    head("История переписки")

    from sqlalchemy import delete as sql_delete

    from app.db import ChannelReceipt, DialogMessage

    CHAT = "qa-77000000000@c.us"

    async def wipe() -> None:
        async with SessionLocal() as session:
            await session.execute(sql_delete(DialogMessage).where(DialogMessage.chat_id == CHAT))
            await session.execute(
                sql_delete(ChannelReceipt).where(ChannelReceipt.message_id.like("qa-%"))
            )
            await session.commit()

    await wipe()

    check("у нового собеседника истории нет", await load_history(SessionLocal, "whatsapp", CHAT) == [])

    turn = [
        {"role": "user", "content": "Сколько стоит?"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1",
                                           "name": "check_availability", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1",
                                      "content": "свободно 3"}]},
        {"role": "assistant", "content": "Comfort — 40 500 тенге."},
    ]
    await save_turn(SessionLocal, "whatsapp", CHAT, turn, already=0)
    saved = await load_history(SessionLocal, "whatsapp", CHAT)
    check("реплики сохранились", len(saved) == 4, str(len(saved)))
    check("порядок не перепутан", saved[0]["content"] == "Сколько стоит?")
    check("вызов инструмента пережил запись",
          isinstance(saved[1]["content"], list) and saved[1]["content"][0]["type"] == "tool_use")
    check("последним идёт ответ", saved[-1]["content"] == "Comfort — 40 500 тенге.")

    await save_turn(SessionLocal, "whatsapp", CHAT,
                    turn + [{"role": "user", "content": "а завтрак?"}], already=4)
    check("дописан только хвост",
          len(await load_history(SessionLocal, "whatsapp", CHAT)) == 5)

    short = await load_history(SessionLocal, "whatsapp", CHAT, depth=2)
    check("глубина ограничивает выдачу", len(short) <= 2, str(len(short)))
    check("история всегда начинается с гостя",
          not short or short[0]["role"] == "user", short[0]["role"] if short else "")

    check("чужая переписка не подмешивается",
          await load_history(SessionLocal, "whatsapp", "qa-другой@c.us") == [])

    check("новое сообщение не повтор", not await seen_before(SessionLocal, "whatsapp", "qa-m1"))
    check("то же сообщение — повтор", await seen_before(SessionLocal, "whatsapp", "qa-m1"))
    check("другое сообщение не повтор", not await seen_before(SessionLocal, "whatsapp", "qa-m2"))
    check("пустой идентификатор не считается", not await seen_before(SessionLocal, "whatsapp", ""))

    await wipe()


async def qa_knowledge() -> None:
    head("Справка об отеле")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"{BASE}/api/knowledge")
            if res.status_code != 200:
                print(f"  ⚠ {BASE}/api/knowledge ответил {res.status_code} — раздел пропущен")
                return
            facts = res.json()
            page = (await client.get(f"{BASE}/nomera")).text
    except Exception as error:  # noqa: BLE001
        print(f"  ⚠ фронтенд недоступен ({error}) — раздел пропущен")
        return

    check("номера пришли", len(facts["rooms"]) >= 5, str(len(facts["rooms"])))

    import re

    digits = re.sub(r"[^0-9]", "", page)
    wrong = [r["slug"] for r in facts["rooms"] if str(r["price"]) not in digits]
    check("цены справки совпадают со страницей", not wrong, ", ".join(wrong))

    doubles = [r for r in facts["rooms"] if r.get("priceDouble", 0) and r["priceDouble"] != r["price"]]
    brief = render_brief(facts)
    for room in doubles:
        check(
            f"«{room['slug']}»: цена за двоих в справке",
            "за двоих" in brief and f"{room['priceDouble']:,}".replace(",", " ") in brief,
        )
    if not doubles:
        print("    (категорий с отдельной ценой за двоих нет)")

    check("телефон в справке", facts["hotel"]["contacts"]["phonePrimary"].startswith("+7"))
    check("реквизиты для сверки платежей на месте", bool(facts["hotel"]["legal"]["bin"]))
    check("координаты выверенные", abs(facts["hotel"]["coordinates"]["lat"] - 43.249) < 0.01)
    check("корпоративный раздел в справке", "korporativnym" in brief)
    check("бриф не разбух", len(brief) < 12000, f"{len(brief)} символов")

    # Категории Exely против категорий сайта: расхождение — сигнал, что отель
    # продаёт то, чего на сайте нет.
    site_slugs = {r["slug"] for r in facts["rooms"]}
    only_in_exely = set(ROOM_TYPES.values()) - site_slugs
    if only_in_exely:
        print(f"    ⚠ Exely продаёт, а на сайте нет: {', '.join(sorted(only_in_exely))}")
    check("все категории сайта известны Exely", site_slugs <= set(ROOM_TYPES.values()),
          ", ".join(sorted(site_slugs - set(ROOM_TYPES.values()))))


async def main() -> int:
    qa_time()
    qa_exely_parsing()
    qa_modes()
    qa_tools()
    qa_payments()
    await qa_hybrid()
    await qa_access()
    await qa_channels()
    await qa_knowledge()

    total = passed + len(failed)
    print(f"\n── Итог ──\n  {passed} из {total}")
    if failed:
        print("  не прошло:")
        for name in failed:
            print(f"    · {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
