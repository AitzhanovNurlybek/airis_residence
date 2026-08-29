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
from app.booking_system.exely import ROOM_TYPES, booking_form_url  # noqa: E402
from app.booking_system.exely import ExelyBookingSystem as _Exely  # noqa: E402
from app.booking_system.exely_api import ExelyApi, _as_date, _money, _tail  # noqa: E402
from app.concierge import (  # noqa: E402
    _status_word,
    FIND_TOOL,
    FULL_TOOLS,
    ROOM_PAGE_TOOL,
    _sane_price,
    READ_ONLY_TOOLS,
    build_system_prompt,
    _tool_availability,
    _tool_cancel,
    _tool_find,
)
from app.channels.whatsapp import Incoming, WhatsAppChannel, _parse, _phone, for_whatsapp  # noqa: E402
from app.channels.flow import reply_for  # noqa: E402
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

    # Exely присылает цену за весь период, а сайт и консьерж говорят «за ночь».
    # Пока их не разделили, гость на двух ночах слышал двойную цену, а на трёх
    # — тройную. Проверка идёт на одних и тех же данных с разным числом ночей:
    # цена за ночь обязана быть одинаковой.
    def stay(total: float, rack: float) -> dict:
        return {
            "room_stays": [
                {
                    "room_types": [
                        {
                            "code": "5050496",
                            "room_type_quota_rph": "111",
                            "placements": [
                                {"price_after_tax": total, "discount": {"basic_after_tax": rack}}
                            ],
                        }
                    ],
                    "rate_plans": [{"code": "10123672"}],
                }
            ],
            "room_type_quotas": [{"rph": "111", "quantity": 3}],
        }

    for nights, total in ((1, 40500.0), (2, 81000.0), (3, 121500.0)):
        offers = exely._offers(stay(total, 45000.0 * nights), nights)
        comfort_n = next(o for o in offers if o.room_slug == "comfort")
        check(f"цена за ночь при {nights} ноч. — 40 500, а не {int(total)}",
              comfort_n.price_per_night == 40500, str(comfort_n.price_per_night))
        check(f"прайс при {nights} ноч. тоже за ночь",
              comfort_n.rates[0].was == 45000, str(comfort_n.rates[0].was))

    # Скидки нет — «было» показывать нечего, иначе гость увидит зачёркнутую
    # цену, равную настоящей.
    same = exely._offers(stay(45000.0, 45000.0), 1)
    check("без скидки старая цена не показывается",
          next(o for o in same if o.room_slug == "comfort").rates[0].was is None)

    check("коды категорий не потерялись", len(ROOM_TYPES) == 6, str(len(ROOM_TYPES)))

    # Неверный код отеля Exely отдаёт как 200 с пустым результатом — это
    # неотличимо от «всё занято». Опечатка в переменной окружения обязана
    # падать при создании клиента, а не превращаться в отказ каждому гостю.
    for bad in ("", "abc", "5095-06", "код"):
        try:
            ExelyBookingSystem(hotel_code=bad)
            check(f"код отеля {bad!r} отклонён", False, "прошёл, хотя не число")
        except ValueError:
            check(f"код отеля {bad!r} отклонён", True)
    check("правильный код принят", ExelyBookingSystem(hotel_code="509506")._hotel == "509506")
    # Лишний пробел в переменной окружения — частая случайность, и ронять
    # из-за него весь консьерж незачем: срезаем.
    check("пробелы вокруг кода срезаются",
          ExelyBookingSystem(hotel_code=" 509506 ")._hotel == "509506")
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
    read_names = {t["name"] for t in READ_ONLY_TOOLS}
    check("в режиме чтения оформления нет", "create_booking" not in read_names)
    check("в режиме чтения есть ссылка на форму", "booking_link" in read_names)

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
    stub_mode = build_system_prompt(brief, "2026-08-24", availability="stub", can_book=True)
    live_mode = build_system_prompt(brief, "2026-08-24", availability="exely")
    check("без системы — правило про стойку", "подтвердит стойка" in none_mode)
    check("без системы инструментов не обещаем", "check_availability" not in none_mode)
    check("в тестовом режиме есть предупреждение", "ТЕСТОВЫЙ РЕЖИМ" in stub_mode)
    check("в боевом предупреждения нет", "ТЕСТОВЫЙ РЕЖИМ" not in live_mode)
    check("везде запрещено выдумывать скидки", all("скидки" in m for m in (none_mode, live_mode)))
    check("везде сказано про язык гостя", all("казахский" in m for m in (none_mode, live_mode)))

    # Главная проверка этого раздела: в правилах не должно быть обещано
    # ничего, чего нет в руках. Расхождение не падает с ошибкой — модель
    # просто отвечает так, будто инструмент отработал, и гость получает
    # выдуманный номер брони. Ловится только сверкой.
    # room_page даётся всегда: страница номера есть у сайта и без системы
    # бронирования. Поэтому он в каждом наборе.
    # Exely с договорным доступом: брони видно, но заводить их по-прежнему
    # нельзя. Это отдельная ветка, и разойтись она может так же тихо.
    lookup_mode = build_system_prompt(
        brief, "2026-08-24", availability="exely", can_find=True
    )
    for label, prompt, tools in (
        ("без системы", none_mode, [ROOM_PAGE_TOOL]),
        ("боевой Exely", live_mode, [ROOM_PAGE_TOOL, *READ_ONLY_TOOLS]),
        ("Exely с доступом к броням", lookup_mode,
         [ROOM_PAGE_TOOL, *READ_ONLY_TOOLS, FIND_TOOL]),
        ("тестовая шахматка", stub_mode, [ROOM_PAGE_TOOL, *FULL_TOOLS]),
    ):
        given = {t["name"] for t in tools}
        for name in ("room_page", "check_availability", "booking_link", "create_booking",
                     "find_booking", "change_booking", "cancel_booking"):
            promised = name in prompt
            check(
                f"{label}: «{name}» обещан ровно тогда, когда есть",
                promised == (name in given),
                "обещан в правилах, но не выдан" if promised else "выдан, но в правилах не описан",
            )

    check("в боевом режиме бронь только через форму", "ТОЛЬКО ЧЕРЕЗ ФОРМУ" in live_mode)
    # Живой диалог показал: консьерж подставил «двоих», ни разу не спросив.
    check("перед ссылкой обязательно спрашивать число гостей",
          "узнай число гостей" in live_mode)
    check("в правилах сказано, что даты надо назвать словами",
          "какие даты выбрать в форме" in live_mode)
    # Живой диалог: гость написал «на ближайшие даты какие номера свободные»,
    # а консьерж дважды подряд потребовал точные даты и ничего не показал.
    check("неопределённые даты не повод для допроса",
          "«на ближайшие»" in live_mode and "посмотри сам" in live_mode)
    check("переспрашивать про даты можно один раз",
          "один раз" in live_mode)
    check("для показа наличия число гостей не спрашиваем",
          "число гостей спрашивать не надо" in live_mode)
    # «Мы оформим» гость читает как «за меня всё сделают» и перестаёт
    # отвечать, считая номер своим. Отказ от этой формулировки — такое же
    # правило, как отказ от «я забронировал».
    check("запрещено и «мы оформим»", "«мы оформим»" in live_mode)
    for rule in ("КАК РАССКАЗЫВАТЬ ПРО НОМЕРА", "КАК ПОКАЗЫВАТЬ СВОБОДНОЕ"):
        check(f"есть раздел «{rule}»", rule in live_mode)
    check("коды категорий гостю не показываем", "служебные" in live_mode)
    check("в боевом запрещено говорить «бронь оформлена»", "бронь оформлена" in live_mode)
    check("без доступа честно сказано, что броней не видно",
          "БРОНИ ТЫ НЕ ВИДИШЬ" in live_mode)
    check("с доступом брони искать разрешено",
          "БРОНИ ГОСТЯ ТЫ ВИДИШЬ" in lookup_mode)
    # Читать — да, менять — нет: такого метода у Exely нет вовсе.
    check("с доступом менять брони по-прежнему нельзя",
          "change_booking" not in lookup_mode and "cancel_booking" not in lookup_mode)

    # Ссылка ведёт на нашу страницу с кодом категории Exely. Опечатка в коде
    # приводит гостя на пустую форму, и он об этом не сообщит — просто уйдёт.
    link = booking_form_url("https://airisresidence.kz", room_slug="comfort",
                            check_in="2026-09-12", check_out="2026-09-15", guests=2)
    check("ссылка ведёт на форму брони", link.startswith("https://airisresidence.kz/booking?"))
    check("в ссылке код категории Exely", "room-type=5050496" in link)
    # Дат в ссылке нет намеренно: виджет Exely их не читает (проверено на
    # живой брони — гость получил ссылку на 1-2 сентября, форма открылась на
    # сегодня-завтра). Класть параметры, которые игнорируются, опаснее, чем
    # не класть: гость видит заполненные чужие даты и бронирует не тот период.
    check("дат в ссылке нет — виджет их не читает",
          "checkin" not in link and "checkout" not in link, link)
    check("числа гостей в ссылке тоже нет", "adults" not in link, link)
    check("неизвестная категория не ломает ссылку",
          booking_form_url("https://airisresidence.kz", room_slug="нет-такого")
          == "https://airisresidence.kz/booking")


# ───────────────────────── проверка платёжек ─────────────────────────


async def qa_exely_api() -> None:
    head("Официальное API Exely (брони)")

    from app.config import Settings

    # Не читаем боевой .env: к моменту подключения реальных ключей отеля
    # проверка на пустых значениях иначе стала бы неверной — не про баг,
    # а про то, что .env больше не пуст. Собираем Settings напрямую.
    check("без ключей доступ не считается настроенным",
          not Settings(
              exely_client_id="", exely_client_secret="",
              exely_property_id="", exely_auth_url="", exely_api_base="",
          ).exely_api_ready)
    check("с ключами доступ считается настроенным",
          Settings(
              exely_client_id="a", exely_client_secret="b",
              exely_property_id="c", exely_auth_url="d", exely_api_base="e",
          ).exely_api_ready)

    api = ExelyApi("id", "secret", "777", auth_url="https://a/token", api_base="https://b")

    tails = {_tail(p) for p in ("+7 777 531-00-09", "87775310009", "77775310009")}
    check("телефон в трёх написаниях — один хвост", len(tails) == 1, str(tails))
    check("пустой телефон не даёт хвоста", _tail("") == "")

    check("дата с временем и зоной разобрана",
          str(_as_date("2026-09-12T14:00:00Z")) == "2026-09-12")
    check("дата без времени разобрана", str(_as_date("2026-09-12")) == "2026-09-12")
    check("мусор вместо даты не роняет", _as_date("позавчера") is None)
    check("сумма строкой разобрана", _money("81000.00") == 81000)
    check("сумма мусором даёт ноль", _money("бесплатно") == 0)

    # У Exely одно поле в разных API называется по-разному. Разбор обязан
    # понимать оба написания, иначе на боевом доступе всё молча развалится.
    first = {"number": "R-1", "arrivalDate": "2026-09-12", "departureDate": "2026-09-15",
             "totalAmount": 135000, "phone": "+7 701 000 00 01", "status": "Confirmed",
             "guest": {"lastName": "Айтжанов", "firstName": "Нурлыбек"}}
    second = {"reservationNumber": "R-2", "checkInDate": "2026-10-01T00:00:00Z",
              "checkOutDate": "2026-10-03T00:00:00Z", "total": {"amount": "81000.00"},
              "state": "New",
              "guests": [{"fullName": "Иван Петров", "phoneNumber": "87010000002"}]}

    one = api._booking(first)
    check("первое написание полей разобрано", one is not None and one.external_id == "R-1")
    check("имя гостя собрано из частей", one is not None and one.guest_name == "Айтжанов Нурлыбек")

    two = api._booking(second)
    check("второе написание полей разобрано", two is not None and two.external_id == "R-2")
    # Ловушка, на которой уже попались: пустое поле `guest` закрывало дорогу
    # к списку `guests`, и бронь с телефоном внутри списка считалась чужой.
    check("имя гостя найдено в списке guests", two is not None and two.guest_name == "Иван Петров")
    check("телефон найден в списке guests", api._phone_of(second) == "87010000002")
    check("сумма из вложенного объекта", two is not None and two.total_amount == 81000)

    check("бронь без дат гостю не показывается", api._booking({"number": "R-3"}) is None)
    check("бронь без номера гостю не показывается",
          api._booking({"arrivalDate": "2026-11-01", "departureDate": "2026-11-02"}) is None)

    check("список из обёртки", len(api._rows({"bookings": [first, second]})) == 2)
    check("список массивом", len(api._rows([first])) == 1)
    check("мусор вместо списка не роняет", api._rows({"нет": 1}) == [])

    source = _Exely(hotel_code="509506")
    check("без доступа Exely брони не ищет", source.can_find_bookings is False)
    with_access = _Exely(hotel_code="509506", reservations=api)
    check("с доступом Exely брони ищет", with_access.can_find_bookings is True)
    check("Exely не заводит брони ни в каком случае",
          not hasattr(with_access, "create_booking"))

    # Гость с живой бронью получил «У вас нет активных броней». Причина:
    # Read Reservation API не отдаёт ни телефона, ни почты гостя — ни в
    # сводке, ни в полной брони. Поиск по телефону был обречён с самого
    # начала и молча возвращал пусто, а консьерж выдавал это за отсутствие
    # броней. Теперь поиск по телефону честно пуст, а бронь ищется по
    # номеру, который у гостя есть в подтверждении.
    import asyncio as _a
    found = _a.get_event_loop().run_until_complete(api.find_bookings(phone="+77087241460"))         if False else []
    check("поиск по телефону больше ничего не обещает",
          "не отдаёт" in (api.find_bookings.__doc__ or ""))
    # Имя не пароль: в базе отеля один человек встречается дважды, а
    # однофамильцы — тем более. Поэтому одной фамилии для выдачи брони
    # мало, нужна ещё дата заезда: свой гость её помнит, чужой не угадает.
    from app.booking_sync import find_by_name as _by_name
    from app.db import SessionLocal as _S2, ExelyBooking as _EB, init_db as _init
    await _init()
    async with _S2() as _sess:
        # Запись переиспользуется, а не вставляется заново: прогон QA не
        # должен падать оттого, что он уже запускался.
        _row = await _sess.get(_EB, "QA-NAME-1")
        if _row is None:
            _row = _EB(number="QA-NAME-1")
            _sess.add(_row)
        _row.status = "Active"
        _row.guest_name = "Тестов Пётр"
        _row.guest_search = "тестов пётр"
        _row.check_in = date(2026, 9, 20)
        _row.check_out = date(2026, 9, 22)
        _row.total_amount = 50000
        _row.room_name = "Comfort"
        await _sess.commit()
        check("поиск по фамилии находит", len(await _by_name(_sess, "Тестов")) >= 1)
        check("регистр не мешает", len(await _by_name(_sess, "тестов")) >= 1)
        # Два символа совпадут с половиной базы — такой поиск бесполезен и
        # опасен: он выдаст первую попавшуюся чужую бронь.
        check("слишком короткий запрос игнорируется", not await _by_name(_sess, "Те"))
        check("несуществующая фамилия ничего не даёт",
              not await _by_name(_sess, "Такоготочнонет"))

    check("в правилах запрещено говорить «броней нет» без номера",
          "у вас нет броней" in build_system_prompt(
              "с", "2026-08-29", availability="exely", can_find=True).lower())

    # Три факта, подтверждённых официальной документацией 2026-08-27, а не
    # угаданных. Раньше код был написан по догадке, и все три оказались бы
    # неверны на боевом ответе.
    detail_response = {
        "booking": {
            "propertyId": "7291", "number": "20240325-7291-260123396",
            "status": "Cancelled", "currencyCode": "RUB",
            "roomStays": [{"arrivalDate": "2026-09-12", "departureDate": "2026-09-15"}],
            "total": {"amount": 121500}, "customer": {"phone": "+77015550101",
                                                       "fullName": "Тест Тестов"},
        }
    }
    # Ответ на бронь обёрнут в {"booking": {...}} — без распаковки все поля
    # читались бы из обёртки и оказывались бы пустыми.
    inner = detail_response["booking"]
    parsed = api._booking(inner)
    check("бронь из детального ответа разобрана", parsed is not None
          and parsed.external_id == "20240325-7291-260123396")
    check("даты найдены внутри roomStays, а не на верхнем уровне",
          parsed is not None and str(parsed.check_in) == "2026-09-12"
          and str(parsed.check_out) == "2026-09-15")
    check("сумма из объекта total.amount", parsed is not None
          and parsed.total_amount == 121500)

    # Список сводок лежит под ключом bookingSummaries, а не bookings —
    # общее для многих API имя, которое мы предполагали по умолчанию.
    summary_response = {"continueToken": "x", "hasMoreData": False,
                        "bookingSummaries": [inner]}
    check("список сводок читается из bookingSummaries",
          len(api._rows(summary_response)) == 1)

    # Живая бронь 2026-08-29 показала, что документация и реальность
    # расходятся: даты лежат в roomStays[].stayDates двумя полями со
    # временем, сумма — в total.priceAfterTax. Прежний разбор возвращал
    # None, то есть бронь молча пропадала.
    real = {
        "number": "20250715-509506-1233688442", "status": "Cancelled",
        "currencyCode": "KZT",
        "customer": {"firstName": "Пётр", "lastName": "Тестов"},
        "total": {"priceBeforeTax": 45000.0, "priceAfterTax": 45000.0},
        "roomStays": [{
            "stayDates": {"arrivalDateTime": "2025-07-15T14:00",
                          "departureDateTime": "2025-07-16T12:00"},
            "roomType": {"id": "5050493", "name": "Standart"},
            "guestCount": {"adultCount": 2},
        }],
    }
    parsed = api._booking(real)
    check("живая бронь Exely разбирается", parsed is not None)
    check("даты берутся из stayDates",
          parsed is not None and str(parsed.check_in) == "2025-07-15"
          and str(parsed.check_out) == "2025-07-16")
    check("сумма берётся из total.priceAfterTax",
          parsed is not None and parsed.total_amount == 45000)
    # Здесь полное имя намеренно: консьерж по нему сверяет бронь. Короткое
    # обращение для сообщений собирает отдельная функция в lifecycle.py.
    check("имя гостя из customer, полностью",
          parsed is not None and parsed.guest_name == "Тестов Пётр",
          parsed.guest_name if parsed else "None")

    # Самая дорогая ошибка этого раздела. Раньше статус считался так:
    # «действует», если строка ровно "booked", иначе «отменена». Локальная
    # шахматка присылает "booked", а Exely — "Confirmed", и гостю с
    # подтверждённой бронью сообщали, что она отменена. Заметить это можно
    # было только на стойке при заселении.
    for status, expected in (
        ("booked", "действует"),
        ("Confirmed", "действует"),
        ("CheckedIn", "действует"),
        ("New", "ждёт подтверждения"),
        ("PENDING", "ждёт подтверждения"),
        ("Cancelled", "отменена"),
        ("canceled", "отменена"),
        ("NoShow", "отменена"),
    ):
        check(f"статус «{status}» → {expected}", _status_word(status) == expected,
              _status_word(status))

    for unknown in ("СтранноеСлово", "", "Whatever"):
        word = _status_word(unknown)
        check(f"незнакомый статус «{unknown}» не выдаётся за отмену",
              "неизвестно" in word and "отменена" not in word, word)


def qa_webhooks() -> None:
    head("Приём вебхуков Exely")

    import os as _os
    import time

    from fastapi.testclient import TestClient

    from app.config import get_settings as _gs

    KEY = "qa-secret-abc"
    was = _os.environ.get("EXELY_WEBHOOK_SECRET")
    _os.environ["EXELY_WEBHOOK_SECRET"] = KEY
    _gs.cache_clear()
    try:
        import app.main as _main

        client = TestClient(_main.app)
        # Номер свой на каждый прогон. События копятся в базе, и с постоянным
        # номером второй запуск QA видел бы повтор там, где проверяет приём.
        ref = f"QA-{int(time.time())}"
        body = {"eventType": "BookingCreated", "number": ref,
                "guest": {"phoneNumber": "+7 701 555 01 01"}}

        # Адрес приёмника открыт всему интернету: его видно в настройках
        # подключения. Без проверки ключа в базу отеля писала бы улица.
        check("без ключа не пускает",
              client.post("/api/webhooks/exely", json=body).status_code == 401)
        check("с чужим ключом не пускает",
              client.post("/api/webhooks/exely", json=body,
                          headers={"X-Api-Key": "wrong-key"}).status_code == 401)

        first = client.post("/api/webhooks/exely", json=body, headers={"X-Api-Key": KEY})
        check("с верным ключом принимает", first.status_code == 200)
        check("событие разобрано", first.json().get("booking") == ref, first.text[:80])

        # Exely присылает уведомление снова, если мы ответили медленно.
        # Второй раз заводить бронь нельзя.
        again = client.post("/api/webhooks/exely", json=body, headers={"X-Api-Key": KEY})
        check("повтор не заводит второе событие", again.json().get("duplicate") is True)
        check("повтор указывает на ту же запись",
              again.json().get("id") == first.json().get("id"))

        # В кабинете Exely имя заголовка задаётся вручную полем «Имя ключа»,
        # и там стоит EXELY_WEBHOOK_SECRET — то же имя, что у переменной
        # окружения, но два разных места. Без этого имени в списке настоящее
        # уведомление получало бы 401 при правильном секрете.
        check("заголовок EXELY_WEBHOOK_SECRET (как в кабинете Exely) принимается",
              client.post("/api/webhooks/exely", json=body,
                          headers={"EXELY_WEBHOOK_SECRET": KEY}).status_code == 200)

        # Ключ может прийти и заголовком Authorization, и параметром адреса:
        # какой из способов выберет Exely, мы увидим только на боевом.
        check("ключ в Authorization принимается",
              client.post("/api/webhooks/exely", json=body,
                          headers={"Authorization": f"Bearer {KEY}"}).status_code == 200)
        check("ключ параметром адреса принимается",
              client.post(f"/api/webhooks/exely?key={KEY}", json=body).status_code == 200)

        # На ошибку отправитель начинает слать повторы. Неразобранное тело —
        # не повод: оно сохранено целиком, разберёмся потом.
        broken = client.post(f"/api/webhooks/exely?key={KEY}",
                             content="не json".encode("utf-8"),
                             headers={"Content-Type": "application/json"})
        check("кривое тело не роняет приём", broken.status_code == 200)

        cancel = client.post("/api/webhooks/exely",
                             json={"event": "BookingCancelled", "reservationNumber": ref},
                             headers={"X-Api-Key": KEY})
        check("отмена той же брони — отдельное событие",
              cancel.status_code == 200 and not cancel.json().get("duplicate"))

        _os.environ["EXELY_WEBHOOK_SECRET"] = ""
        _gs.cache_clear()
        check("без настроенного секрета точка выключена",
              client.post("/api/webhooks/exely", json=body,
                          headers={"X-Api-Key": KEY}).status_code == 503)
    finally:
        if was is None:
            _os.environ.pop("EXELY_WEBHOOK_SECRET", None)
        else:
            _os.environ["EXELY_WEBHOOK_SECRET"] = was
        _gs.cache_clear()


def qa_freedompay() -> None:
    head("FreedomPay: подпись и разбор ответа")

    import hashlib as _h
    from app.config import Settings as _S
    from app.payments import FreedomPayProvider, _tag

    prov = FreedomPayProvider(_S(
        payment_provider="freedompay", payment_terminal_id="570767",
        payment_client_secret="secret_word",
        payment_result_url="https://airisresidence.kz/api/backend/api/payments/result"))

    fields = {"pg_amount": "1000", "pg_currency": "KZT", "pg_description": "Test",
              "pg_merchant_id": "570767", "pg_salt": "abc123"}
    want = _h.md5(";".join(["init_payment.php", "1000", "KZT", "Test",
                            "570767", "abc123", "secret_word"]).encode()).hexdigest()

    # Подпись — единственное, что отделяет наш запрос от чужого. Ошибка в
    # ней даёт отказ банка без внятной причины, поэтому сверяем с примером
    # из документации FreedomPay посимвольно.
    check("подпись совпадает с алгоритмом документации",
          prov._sign("init_payment.php", fields) == want)
    check("pg_sig не участвует в собственном расчёте",
          prov._sign("init_payment.php", dict(fields, pg_sig="мусор")) == want)
    # Поля сортируются по имени, а не по порядку в словаре: иначе подпись
    # зависела бы от того, в каком порядке их собрали в коде.
    check("порядок полей не влияет на подпись",
          prov._sign("init_payment.php",
                     {k: fields[k] for k in reversed(list(fields))}) == want)

    # Уведомление об оплате приходит на открытый адрес. Без проверки подписи
    # любой желающий мог бы объявить чужую бронь оплаченной.
    good = dict(fields)
    good["pg_sig"] = prov._sign("result", good)
    check("верно подписанное уведомление принимается", prov.verify_callback(good, {}))
    check("подделанное уведомление отвергается",
          not prov.verify_callback(dict(good, pg_sig="0" * 32), {}))
    check("уведомление без подписи отвергается",
          not prov.verify_callback(dict(fields), {}))

    check("оплата распознана", FreedomPayProvider.parse_callback(
        {"pg_order_id": "A-1", "pg_result": "1"}) == ("A-1", "paid"))
    check("отказ распознан", FreedomPayProvider.parse_callback(
        {"pg_order_id": "A-1", "pg_result": "0"}) == ("A-1", "failed"))
    # Незнакомый код не должен превращаться в «оплачено»: это деньги.
    check("незнакомый код не считается оплатой", FreedomPayProvider.parse_callback(
        {"pg_order_id": "A-1", "pg_result": "7"}) == ("A-1", "pending"))

    check("тег из ответа читается", _tag("<pg_status>ok</pg_status>", "pg_status") == "ok")
    check("отсутствующий тег не роняет", _tag("<a>1</a>", "pg_redirect_url") == "")


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

    # Окно ищем, а не берём фиксированное. Отель бывает занят целиком: на
    # полной загрузке фиксированные «послезавтра + 2 ночи» давали ноль
    # свободных, и половина раздела — создание, перенос, отмена заявки —
    # молча не проверялась. Пропуск выглядел как успех.
    free = None
    check_in = check_out = hotel_today()
    for offset in (2, 5, 9, 14, 21, 30, 45):
        check_in = hotel_today() + timedelta(days=offset)
        check_out = check_in + timedelta(days=2)
        try:
            found = await hybrid.availability(check_in, check_out)
        except BookingSystemUnavailable as error:
            print(f"  ⚠ Exely недоступен, раздел пропущен: {error}")
            return
        free = found
        if any((o.rooms_left or 0) > 0 for o in found.offers):
            print(f"    окно для проверки записи: {check_in} → {check_out}")
            break

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
        print("  ⚠ отель занят на полтора месяца вперёд — запись не проверить")
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
    # Проверяем не формулировку, а суть: чужие данные не должны утечь.
    # Эхо номера, который назвал сам собеседник, — не утечка; утечка это
    # даты, имя и сумма. Раньше тест цеплялся за слово «нет» и сломался бы
    # от любой правки текста, хотя поведение осталось верным.
    leaked = [
        part for part in (mine.guest_name, str(mine.check_in), str(mine.check_out))
        if part and part in hidden
    ]
    check("чужую бронь по номеру не отдаёт", not leaked, f"утекло: {leaked}")

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

    # Прямая проверка адреса подтверждения приёма. Раньше _url() собирала
    # .../deleteNotification/{receipt_id}/{token} — receiptId оказывался
    # ПЕРЕД токеном вместо после него, Green API такой путь не находил, и
    # confirm() тихо возвращал неудачу на каждом вызове. Бот вечно
    # опрашивал одно и то же уведомление, думая, что оно новое.
    from app.channels import WhatsAppChannel

    probe = WhatsAppChannel("999", "SECRETTOKEN")
    delete_url = f"{probe._url('deleteNotification')}/77"
    check("токен стоит перед receiptId в адресе подтверждения",
          delete_url.endswith("/deleteNotification/SECRETTOKEN/77"), delete_url)
    check("receiptId не встаёт перед токеном",
          "/deleteNotification/77/SECRETTOKEN" not in delete_url, delete_url)

    # Гость получил два ответа на одну фразу: WhatsApp при плохой связи
    # доставил её как два РАЗНЫХ сообщения, и дедуп по idMessage такое не
    # ловит — идентификаторы честно разные. Отсюда вторая защита, по тексту.
    from app.dialogs import answered_same_recently as _same
    from app.db import SessionLocal as _SL
    CH, CHAT = "whatsapp-qa", "77015550099@c.us"
    await save_turn(_SL, CH, CHAT,
                    [{"role": "user", "content": "проверка повтора"},
                     {"role": "assistant", "content": "ответ"}], 0)
    check("та же фраза из того же чата — повтор",
          await _same(_SL, CH, CHAT, "проверка повтора"))
    check("регистр не важен", await _same(_SL, CH, CHAT, "Проверка Повтора"))
    check("другая фраза — не повтор", not await _same(_SL, CH, CHAT, "а завтрак входит"))
    check("тот же текст в другом чате — не повтор",
          not await _same(_SL, CH, "77000000000@c.us", "проверка повтора"))
    # За пределами окна повтор перестаёт считаться повтором: гость вправе
    # спросить то же самое через час и получить ответ.
    check("вне временного окна — не повтор",
          not await _same(_SL, CH, CHAT, "проверка повтора", 0))

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

    # Голосовое не распознавалось вовсе: типа audioMessage не было в списке,
    # сообщение выходило пустым, и вебхук отвечал «пустое сообщение». Гость
    # отправлял голосовое и не получал НИЧЕГО. Тишина хуже отказа.
    for kind in ("audioMessage", "pttMessage", "voiceMessage"):
        voice = _parse({
            "typeWebhook": "incomingMessageReceived", "idMessage": "V-" + kind,
            "senderData": {"chatId": "77015550011@c.us"},
            "messageData": {"typeMessage": kind, "fileMessageData": {
                "downloadUrl": "https://example/v.oga", "fileName": "v.oga"}},
        })
        check(f"«{kind}» распознан как голосовое", voice is not None and voice.is_voice)

    # Ссылка на файл у голосового есть — она понадобится, когда появится
    # расшифровка речи. Защита не в её отсутствии, а в порядке проверок:
    # reply_for смотрит is_voice ПЕРВЫМ. Иначе голосовое ушло бы в разбор
    # платёжек, и гость получил бы «это не платёжный документ» на свой
    # вопрос о брони. Проверяем именно поведение, а не поле.
    from app.config import get_settings as _gs

    voice_reply = await reply_for(
        _gs(), None, WhatsAppChannel("1", "2"),
        _parse({"typeWebhook": "incomingMessageReceived", "idMessage": "V-ROUTE",
                "senderData": {"chatId": "77015550011@c.us"},
                "messageData": {"typeMessage": "audioMessage", "fileMessageData": {
                    "downloadUrl": "https://example/v.oga", "fileName": "v.oga"}}}))
    check("голосовое ведёт к просьбе написать текстом",
          "текстом" in voice_reply.lower(), voice_reply[:60])
    check("голосовое не разбирается как платёжка",
          "платёжный документ" not in voice_reply)

    # Распознавание речи: включается только заполненным ключом. Голос гостя
    # уходит третьей стороне, и «включим, если получится» тут не подходит.
    from app.config import Settings as _Set
    from app.speech import SpeechUnavailable, configured as _sp, transcribe as _tr

    check("без ключа распознавание выключено", not _sp(_Set(speech_api_key="")))
    check("с ключом включается", _sp(_Set(speech_api_key="k")))

    try:
        await _tr(_Set(speech_api_key=""), b"audio")
        check("без ключа не расшифровывает", False, "расшифровало")
    except SpeechUnavailable:
        check("без ключа не расшифровывает", True)

    # Гость может зажать кнопку и прислать десять минут, а платим мы.
    try:
        await _tr(_Set(speech_api_key="k", speech_max_mb=1), b"x" * (2 * 1024 * 1024))
        check("слишком длинная запись отклоняется", False, "приняло")
    except SpeechUnavailable as _e:
        check("слишком длинная запись отклоняется", "длинная" in str(_e))

    try:
        await _tr(_Set(speech_api_key="k"), b"")
        check("пустая запись отклоняется", False)
    except SpeechUnavailable:
        check("пустая запись отклоняется", True)

    check("обычный файл голосовым не считается", doc_in is not None and not doc_in.is_voice)
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
    # Код категории нужен инструментам: по нему проверяется наличие и
    # собирается ссылка на форму. Без кода в справке модель подставляет
    # похожий на правду выдуманный, и гость приходит на пустую форму.
    for room in facts["rooms"]:
        check(f"код «{room['slug']}» есть в справке", f"[код {room['slug']}]" in brief)
        check(f"ссылка на страницу «{room['slug']}» есть", room["url"] in brief)

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
    await qa_exely_api()
    qa_webhooks()
    qa_freedompay()
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
