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
    AVAILABILITY_TOOL,
    FIND_TOOL,
    FULL_TOOLS,
    FIRST_ACTION,
    READ_ONLY_TOOLS,
    ROOM_PAGE_TOOL,
    _tool_room_page,
    _sane_price,
    READ_ONLY_TOOLS,
    build_system_prompt,
    _tool_availability,
    _tool_cancel,
    _tool_find,
)
from app.channels.whatsapp import Incoming, WhatsAppChannel, _parse, _phone, for_whatsapp  # noqa: E402
from app.webhooks_api import UNREADABLE  # noqa: E402
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


async def qa_tools() -> None:
    head("Инструменты консьержа")

    names = {t["name"] for t in FULL_TOOLS}
    # Пять своих для шахматки плюс просьба на стойку — она нужна в любом режиме.
    check("полный набор — шесть инструментов", len(FULL_TOOLS) == 6, str(len(FULL_TOOLS)))
    check("есть проверка наличия", "check_availability" in names)

    # Одноместный номер Exely показывает ТОЛЬКО при запросе на одного гостя.
    # Пока в запрос была зашита жёсткая двойка, Standart Single всегда
    # считался занятым, и гостю, приехавшему одному, самый дешёвый номер не
    # предлагался никогда. Проверено 2026-09-02 на живом движке: на 20
    # сентября на одного он свободен (2 шт.), на двоих его нет в ответе.
    import inspect as _insp  # noqa: PLC0415

    from app.booking_system.exely import ExelyBookingSystem as _EBS  # noqa: PLC0415

    схема = (AVAILABILITY_TOOL["input_schema"]["properties"])
    check("инструмент спрашивает число гостей", "guests" in схема)
    check("и объясняет, зачем оно нужно",
          "одномест" in схема.get("guests", {}).get("description", ""),
          схема.get("guests", {}).get("description", "")[:80])

    исходник = _insp.getsource(_EBS.availability)
    check("число гостей уходит в запрос, а не зашито",
          '"criterions[0].adults": "2"' not in исходник
          and "adults" in исходник and "guests" in исходник)
    check("гостей передаёт и обработчик инструмента",
          "guests=" in _insp.getsource(_tool_availability))

    # ── «Мест нет» не должно быть концом разговора ─────────────────────
    #
    # Просьба отеля, и причина у неё деловая: наличие в системе неточно в
    # обе стороны. Часть номеров отель держит в резерве, а снятую бронь из
    # шахматки убирают не сразу — «занято» в системе не означает «занято в
    # отеле». Гость, услышавший голый отказ, просто уходит.
    from datetime import date as _d  # noqa: PLC0415

    from app.booking_system.base import Availability, RoomOffer  # noqa: PLC0415

    class _ВсёЗанято:
        async def availability(self, check_in, check_out, *, guests=2):  # noqa: ANN001
            пусто = [
                RoomOffer(room_slug="standart", room_name="Standart", rooms_left=0,
                          price_per_night=None, source="exely", rates=()),
                RoomOffer(room_slug="comfort", room_name="Comfort", rooms_left=0,
                          price_per_night=None, source="exely", rates=()),
            ]
            return Availability(check_in, check_out, 1, пусто, "exely")

    факты = {"hotel": {"contacts": {"phonePrimary": "+7 (777) 531-00-09"}},
             "rooms": []}
    вывод = await _tool_availability(
        _ВсёЗанято(), {"check_in": "2026-09-05", "check_out": "2026-09-06"}, факты)
    check("при полной занятости сказано не обрывать разговор",
          "Не заканчивай разговор отказом" in вывод, вывод[-200:])
    check("телефон стойки попадает в подсказку",
          "531-00-09" in вывод, вывод[-200:])
    check("резерв упомянут", "резерв" in вывод, вывод[-160:])
    check("обещать номер запрещено", "нельзя" in вывод, вывод[-160:])

    # А когда номера есть — никакой подсказки быть не должно: она сбивала бы
    # разговор на телефон там, где бот и так отвечает.
    class _ЕстьНомера(_ВсёЗанято):
        async def availability(self, check_in, check_out, *, guests=2):  # noqa: ANN001
            есть = [RoomOffer(room_slug="standart", room_name="Standart", rooms_left=3,
                              price_per_night=36000, source="exely", rates=())]
            return Availability(check_in, check_out, 1, есть, "exely")

    вывод2 = await _tool_availability(
        _ЕстьНомера(), {"check_in": "2026-09-20", "check_out": "2026-09-21"}, факты)
    check("при свободных номерах подсказки про телефон нет",
          "Не заканчивай разговор отказом" not in вывод2, вывод2[-160:])

    # Троих взрослых Exely в один номер не продаёт ни в одной категории, и
    # ответ выглядел как «всё занято». Семья «двое взрослых и ребёнок 4 лет»,
    # посчитанная как трое, слышала «занято» (замерено 2026-10-05).
    class _ТолькоНаДвоих(_ВсёЗанято):
        async def availability(self, check_in, check_out, *, guests=2):  # noqa: ANN001
            сколько = 4 if guests <= 2 else 0
            return Availability(check_in, check_out, 1, [
                RoomOffer(room_slug="comfort", room_name="Comfort", rooms_left=сколько,
                          price_per_night=45000, source="exely", rates=())], "exely")

    на_троих = await _tool_availability(
        _ТолькоНаДвоих(), {"check_in": "2026-11-20", "check_out": "2026-11-21", "guests": 3}, факты)
    check("троим взрослым — не «всё занято», а честно про двоих в номере",
          "НЕ «всё занято»" in на_троих and "свободно 4" in на_троих
          and "СВОБОДНЫХ НЕТ НИ В ОДНОЙ" not in на_троих, на_троих[:160])
    check("и подсказка пересчитать без детей до 6 лет", "младше 6" in на_троих)
    на_двоих = await _tool_availability(
        _ТолькоНаДвоих(), {"check_in": "2026-11-20", "check_out": "2026-11-21", "guests": 2}, факты)
    check("на двоих — обычный список без пометки", "НЕ «всё занято»" not in на_двоих)
    гости = AVAILABILITY_TOOL["input_schema"]["properties"]["guests"]["description"]
    check("детей младше 6 в число гостей не считать", "младше 6 НЕ считай" in гости)

    # Правила должны говорить то же самое: подсказка в выводе сильнее, но
    # разговор заканчивается телефоном и там, где инструмент не звучал.
    правила = build_system_prompt("", "2026-09-02", availability="exely")
    check("в правилах сказано заканчивать разговор телефоном",
          "ЧЕМ ЗАКАНЧИВАТЬ РАЗГОВОР" in правила)
    check("и сказано, что отказ — не конец разговора",
          "отказ — не конец разговора" in правила.lower())

    # Первое, что видит гость. На голое «Здравствуйте» бот отвечал «Чем я
    # могу вам помочь?» — дежурная фраза колл-центра: она ничего не двигает
    # и заставляет гостя придумывать вопрос самому. Заказчик это заметил
    # первым же живым сообщением на новый номер.
    check("в правилах сказано, чем отвечать на голое приветствие",
          "только поздоровался" in правила)
    check("и прямо запрещена дежурная фраза",
          "Чем я могу вам помочь" in правила and "колл-центра" in правила)

    # ── Гость по корпоративному договору ───────────────────────────────
    #
    # У компании свои цены, и до этого бот про договоры не знал: сотрудник
    # слышал в переписке прайс, а в кабинете видел договорную цену. Хуже
    # того, бот отправлял его на публичную форму — то есть на оплату картой
    # по прайсу, мимо договора и без счёта для бухгалтерии.
    import time as _t  # noqa: PLC0415

    from sqlalchemy import delete as _del2  # noqa: PLC0415

    from app.corp_guest import _tail, find_corporate, price_for  # noqa: PLC0415
    from app.config import Settings as _S  # noqa: PLC0415
    from app.concierge import _tool_link  # noqa: PLC0415
    from app.db import Company, CompanyRate, CompanyUser  # noqa: PLC0415

    # Один и тот же номер записывают по-разному — узнавать надо все записи.
    хвосты = {_tail(x) for x in ("+7 701 555 77 99", "77015557799",
                                 "8 (701) 555-77-99", "7 701-555-7799")}
    check("телефон узнаётся в любой записи", len(хвосты) == 1, str(хвосты))
    check("короткий номер не даёт ложных совпадений", _tail("12345") == "")

    # Точная цена из договора важнее процента, иначе скидка от стойки
    # отменяла бы то, о чём договорились по конкретной категории.
    корп = {"discount_percent": 15, "rates": {"comfort": 38000}}
    check("процент применяется", price_for(корп, "standart", 40000) == 34000,
          str(price_for(корп, "standart", 40000)))
    check("точная цена важнее процента",
          price_for(корп, "comfort", 45000) == 38000)
    check("цена округляется вниз до сотни",
          price_for(корп, "standart-single", 35000) == 29700,
          str(price_for(корп, "standart-single", 35000)))

    ФАКТЫ = {"hotel": {"url": "https://airisresidence.kz"},
             "rooms": [{"slug": "standart", "name": "Standart", "price": 40000}]}

    # Публичная форма берёт карту по прайсу — корпоративному она не подходит.
    ссылка_корп = _tool_link(_S(), ФАКТЫ, {"room": "standart"},
                             corporate={"company": 'ТОО "Компас"',
                                        "manager_name": "Айнур",
                                        "manager_phone": "+7 701 930 0370"})
    check("корпоративного ведём в кабинет",
          "airisresidence.kz/corp" in ссылка_корп, ссылка_корп[:90])
    check("и НЕ на публичную форму",
          "/booking" not in ссылка_корп, ссылка_корп[:90])
    check("менеджер компании назван", "Айнур" in ссылка_корп)

    ссылка_обычная = _tool_link(_S(), ФАКТЫ, {"room": "standart"})
    check("обычному гостю по-прежнему публичная форма",
          "/booking?room-type=" in ссылка_обычная, ссылка_обычная[:90])

    # Наличие: договорная цена вместо тарифов Exely.
    вывод_корп = await _tool_availability(
        _ЕстьНомера(), {"check_in": "2026-09-20", "check_out": "2026-09-21"},
        ФАКТЫ, corporate=корп)
    check("в наличии показана цена по договору",
          "по договору: 34000" in вывод_корп, вывод_корп[-220:])

    # Категория без договорной цены: выдумывать нельзя.
    без_цены = await _tool_availability(
        _ЕстьНомера(), {"check_in": "2026-09-20", "check_out": "2026-09-21"},
        {"hotel": {"url": "x"}, "rooms": []}, corporate=корп)
    check("без цены в договоре отправляем к менеджеру",
          "назовёт менеджер" in без_цены, без_цены[-200:])

    # Узнавание по базе. Ошибиться в сторону «принять чужого за своего»
    # нельзя: это выдача условий чужого договора постороннему.
    СЛАГ = f"qa-corp-{int(_t.time())}"
    ТЕЛЕФОН = f"+7 701 000 {int(_t.time()) % 10000:04d}"
    try:
        async with SessionLocal() as ses:
            комп = Company(slug=СЛАГ, name="QA Компания", discount_percent=10,
                           is_active=True)
            ses.add(комп)
            await ses.flush()
            ses.add(CompanyUser(company_id=комп.id, email=f"{СЛАГ}@qa.kz",
                                full_name="QA Сотрудник", phone=ТЕЛЕФОН,
                                is_active=True))
            await ses.commit()
            айди = комп.id

        нашли = await find_corporate(ТЕЛЕФОН)
        check("сотрудник компании узнан",
              (нашли or {}).get("company") == "QA Компания", str(нашли)[:80])
        check("посторонний остаётся обычным гостем",
              await find_corporate("+7 999 111 22 33") is None)

        # Два человека с одним телефоном — не знаем, кто именно пишет.
        async with SessionLocal() as ses:
            ses.add(CompanyUser(company_id=айди, email=f"{СЛАГ}-2@qa.kz",
                                full_name="Двойник", phone=ТЕЛЕФОН,
                                is_active=True))
            await ses.commit()
        check("при двух совпадениях договор не применяем",
              await find_corporate(ТЕЛЕФОН) is None)

        # Компанию отключили — договор больше не действует.
        async with SessionLocal() as ses:
            await ses.execute(_del2(CompanyUser).where(
                CompanyUser.email == f"{СЛАГ}-2@qa.kz"))
            комп = await ses.get(Company, айди)
            комп.is_active = False
            await ses.commit()
        check("у отключённой компании цен нет",
              await find_corporate(ТЕЛЕФОН) is None)
    finally:
        async with SessionLocal() as ses:
            await ses.execute(_del2(CompanyRate).where(
                CompanyRate.company_id == айди))
            await ses.execute(_del2(CompanyUser).where(
                CompanyUser.company_id == айди))
            await ses.execute(_del2(Company).where(Company.id == айди))
            await ses.commit()
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
                     "find_booking", "change_booking", "cancel_booking", "front_desk_request"):
            promised = name in prompt
            check(
                f"{label}: «{name}» обещан ровно тогда, когда есть",
                promised == (name in given),
                "обещан в правилах, но не выдан" if promised else "выдан, но в правилах не описан",
            )

    check("в боевом режиме бронь только через форму", "ТОЛЬКО ЧЕРЕЗ ФОРМУ" in live_mode)

    # Инструкцию себе консьерж читает на «ты» и переносил это на гостя.
    # Замерено 2026-08-30 на двенадцати ответах: каждый четвёртый уходил с
    # «пришли номер брони» и «назови фамилию». Для отеля это заметно сразу.
    check("к гостю обращаются на «вы»", "Гостю — всегда на «вы»" in live_mode)
    # Бот зеркалил тон гостя: на «привет» и «хай» отвечал «Привет!». Замерено
    # 2026-09-01 на шестнадцати приветствиях — так уходила половина. Гость
    # может позволить себе панибратство, отель не может.
    check("здоровается всегда вежливо: «Здравствуйте» / «Hello»",
          "Здоровайся всегда вежливо" in live_mode and "«Hello»" in live_mode)

    # Правило про приветствие тон в СЕРЕДИНЕ разговора не удержало. Живой
    # случай 2026-09-01: гостья написала «крутой номер табайык )», и
    # консьерж ответил «Хахаха, слышу вас! Comfort Plus — самый кайф».
    # Разговор двух приятелей, а не письмо отеля.
    #
    # Воспроизводилось только с историей переписки: бот подхватывает уже
    # сложившуюся манеру, а на одиночном сообщении отвечает ровно. Замер на
    # настоящей истории: было 2 из 4, после правила в тексте — 1 из 4, после
    # переноса в конец промпта — 0 из 6. Шестой случай, когда место решает.
    check("тон держится весь разговор, а не только в начале",
          "Пишет отель, а не приятель" in live_mode)
    check("названы слова, которые подхватывать нельзя",
          "«кайф»" in live_mode and "«круто»" in live_mode)
    check("разница между тёплым и фамильярным проговорена",
          "Тёплым быть можно, фамильярным нельзя" in live_mode)
    check("названы приветствия, на которые тянет ответить так же",
          "«привет», «хай» и «салам»" in live_mode)

    # «Отменила бронь, где деньги» — вопрос, который задают уже нервничая, и
    # отвечать на него уточняющим вопросом нельзя. Сроки подтверждены
    # поддержкой платёжной системы 2026-08-31.
    check("срок возврата называется сразу", "1–7 рабочих дней" in live_mode)

    # Отменить бронь консьерж не может — в Exely нет метода записи. Раньше он
    # говорил «позвоните на стойку», и просьба на этом умирала: гость,
    # написавший ночью, либо звонил утром сам, либо просто не приезжал, а
    # отель узнавал о пустом номере в день заезда.
    from app.concierge import CANCEL_REQUEST_TOOL  # noqa: PLC0415

    check("просьбу об отмене есть чем передать",
          CANCEL_REQUEST_TOOL in READ_ONLY_TOOLS)
    check("передавать просьбу можно и без номера брони",
          not CANCEL_REQUEST_TOOL["input_schema"].get("required"))
    check("инструмент не выдаёт себя за отмену",
          "только передаёт просьбу" in CANCEL_REQUEST_TOOL["description"])

    # Замер 2026-08-31: пока правило лежало в описании инструмента, просьбу
    # передавали 1–2 раза из 4 — бот сначала спрашивал номер брони. После
    # переноса в конец промпта — 4 из 4 на четырёх формулировках, и 0 из 4
    # там, где отмены нет («а какие условия отмены?»). Четвёртый случай за
    # три дня, когда место правила решает больше его слов.
    check("передавать просьбу велено первым действием",
          "ПЕРВЫМ ДЕЙСТВИЕМ вызови cancel_request" in live_mode)
    check("номер брони не повод откладывать передачу",
          "не дожидаясь номера брони" in live_mode)
    check("сказано, чем плохо промолчать",
          "о пустом номере узнают в день заезда" in live_mode)
    check("сказано, что задержка не на стороне отеля",
          "зависит от банка гостя" in live_mode)
    # Платежи идут мимо нас: доступа к ним нет, и обещать проверку возврата
    # значит повторить ровно ту ошибку, которую весь день исправляли.
    check("проверять возврат консьерж не обещает",
          "проверить, ушёл ли возврат и где он сейчас, ты НЕ МОЖЕШЬ" in live_mode)
    check("вместо обещания сказано, что нужно стойке",
          "последние четыре цифры карты" in live_mode)
    check("названы формы, на которых случаются срывы",
          "«пришлите»" in live_mode and "«назовите»" in live_mode)

    # Напоминание порядка стоит последним — и это не вкусовщина, а замер.
    # 2026-08-29, шесть повторов каждого вопроса: пока блока не было,
    # «есть номер на завтра» вызывал проверку 3 раза из 6, «что свободно на
    # выходных» — 2 из 6. С блоком оба стали 6 из 6. Причина позиционная:
    # правила выдачи ссылки идут после правил наличия, и «узнай число гостей»
    # побеждало по свежести. Если блок уедет с конца, эффект пропадёт молча —
    # поэтому проверяем именно место.
    check("напоминание порядка стоит последним",
          live_mode.rstrip().endswith(FIRST_ACTION.rstrip()),
          live_mode.rstrip()[-60:])
    check("первым действием — проверка наличия",
          "ПЕРВЫМ ДЕЙСТВИЕМ вызови check_availability" in live_mode)
    check("анкету до проверки не устраивают",
          "Ни числа гостей, ни даты выезда, ни категории до этого не спрашивай" in live_mode)
    check("расплывчатые даты консьерж выводит сам",
          "«на выходных» — ближайшие суббота и воскресенье" in live_mode)
    # Цена из тарифа ниже прайса в справке, и модель охотно сочиняла причину:
    # «на эти выходные действует скидка» — при том что 1 сентября 2026 вторник.
    # Выдуманное условие гость запомнит и сошлётся на него.
    check("причину цены выдумывать нельзя",
          "не объясняй, почему она такая" in live_mode)
    check("названы выдумки, которые встречались",
          "«скидка»" in live_mode and "«акция»" in live_mode)
    # Без системы наличия проверять нечем — и блока быть не должно.
    check("без наличия напоминания о проверке нет", "ПЕРЕД ОТВЕТОМ" not in none_mode)

    # Живой диалог 2026-08-29 закончился вопросом «а кто хозяин гостиницы или
    # хозяйка». Правила об этом молчали, и ответ выходил каждый раз разный.
    # Имена владельца и сотрудников — личные данные людей, и раздаёт их отель
    # сам. А вот юрлицо опубликовано в реквизитах сайта, и скрывать его
    # незачем: без него корпоративный клиент не выставит договор.
    check("имена владельца и персонала не разглашаются",
          "Имён владельца, руководства и сотрудников не называй" in live_mode)
    check("подсказанное гостем имя не повод его подтвердить",
          "гость говорит, что уже знает" in live_mode)
    check("юрлицо и реквизиты назвать можно",
          "опубликованы на сайте" in live_mode)
    check("за вопросом о владельце часто стоит жалоба",
          "стойк" in live_mode.lower() and "что случилось" in live_mode)
    check("просьба выйти на руководство — повод позвать человека",
          "просьба выйти на владельца, руководство или конкретного сотрудника" in live_mode)

    # Тот же диалог: гость написал «фото номера можно» и получил столбик
    # ссылок. Просил он картинки, а ссылка в переписке — это предложение
    # открыть четыре вкладки, то есть отказ, оформленный как ответ.
    photo_room = {"rooms": [{
        "slug": "comfort", "name": "Комфорт", "url": "https://airisresidence.kz/nomera/comfort",
        "area": "22 м²", "beds": "кровать",
        "images": ["https://media/1.jpg", "https://media/2.jpg", "/относительный.jpg"],
    }]}
    queue: list = []
    said = _tool_room_page(photo_room, {"room": "comfort"}, queue)
    check("снимки номера уходят в отправку", len(queue) == 2, f"в очереди {len(queue)}")
    check("относительные пути в отправку не попадают",
          all(p["url"].startswith("http") for p in queue))
    check("к снимку приложено название категории",
          all(p["room"] == "Комфорт" for p in queue))
    check("модель знает, что снимки отправлены", "Снимков отправлено: 2" in said, said[:60])
    check("ссылка на страницу остаётся", "/nomera/comfort" in said)
    check("очередь снимков не растёт на неизвестной категории",
          _tool_room_page(photo_room, {"room": "нет-такой"}, queue) and len(queue) == 2)
    check("без снимков вызов не падает",
          "Снимков" not in _tool_room_page(
              {"rooms": [{"slug": "a", "name": "A", "url": "u", "area": "", "beds": ""}]},
              {"room": "a"}, []))
    check("инструмент обещает снимки, а не только ссылку",
          "снимки уходят в переписку сами" in ROOM_PAGE_TOOL["description"])
    # Живой диалог показал: консьерж подставил «двоих», ни разу не спросив.
    check("перед ссылкой обязательно спрашивать число гостей",
          "узнай число гостей" in live_mode)
    check("в правилах сказано, что даты надо назвать словами",
          "Назови словами даты, категорию и число гостей" in live_mode)
    check("и что форма откроется уже заполненной", "уже заполненной" in live_mode)
    check("и что делать, если даты в ссылку не попали",
          "какие даты выбрать в форме" in live_mode)
    # Имя спрашивали ДО ссылки — лишний шаг между «беру» и формой, на котором
    # гость может уйти. Теперь ссылка сразу, вопрос об имени — в том же
    # сообщении (решение 2026-10-05).
    check("ссылка сразу, без вопросов перед ней", "ссылку на бронирование давай сразу" in live_mode)
    check("имя — последней строкой того же сообщения",
          "В том же сообщении, последней строкой, спроси, на чьё имя" in live_mode)
    check("старого «спроси имя перед ссылкой» больше нет",
          "Перед тем как дать ссылку на бронирование, спроси" not in live_mode)
    # Живой диалог: гость написал «на ближайшие даты какие номера свободные»,
    # а консьерж дважды подряд потребовал точные даты и ничего не показал.
    check("неопределённые даты не повод для допроса",
          "«на ближайшие»" in live_mode and "посмотри сам" in live_mode)
    check("переспрашивать про даты можно один раз",
          "один раз" in live_mode)
    # Живой диалог 2026-08-29, 19:42: на вопрос «есть номер на завтра?»
    # консьерж ответил «завтра есть номера», начал уточнять детали — и через
    # две минуты, уже вызвав инструмент, сообщил, что занято всё. Гость успел
    # поверить и получил отказ. Наличие проверено: 30 августа действительно
    # свободных не было, то есть первый ответ был выдуман.
    check("про наличие нельзя говорить до вызова инструмента",
          "пока не вызвал инструмент" in live_mode)
    check("названы запрещённые формулировки",
          "«да, есть»" in live_mode and "«свободно»" in live_mode)
    check("«на завтра» разворачивается в даты без переспроса",
          "«На завтра» — это завтра плюс одна ночь" in live_mode)
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
    from datetime import date as _d  # noqa: PLC0415

    from app.booking_system.exely import stay_for_link  # noqa: PLC0415

    сегодня = _d(2026, 10, 5)
    link = booking_form_url("https://airisresidence.kz", room_slug="comfort",
                            check_in="2026-10-20", check_out="2026-10-22", guests=1,
                            lang="en", today=сегодня)
    check("ссылка ведёт на форму брони", link.startswith("https://airisresidence.kz/booking?"))
    check("в ссылке код категории Exely", "room-type=5050496" in link)
    # Даты виджет читает как date + nights — проверено на живой форме
    # 2026-10-05: «?date=2026-10-20&nights=2&adults=1» открыл форму на
    # «20 октября — 22 октября, 2 ночи, 1 гость». До этого почти два месяца
    # считалось, что дат он не читает вовсе, и гость выставлял их руками.
    check("в ссылке день заезда", "date=2026-10-20" in link, link)
    check("и число ночей", "nights=2" in link, link)
    check("и взрослые", "adults=1" in link, link)
    check("и язык гостя", "lang=en" in link, link)
    с_метками = booking_form_url("https://airisresidence.kz", room_slug="comfort",
                                 utm_source="whatsapp", today=сегодня)
    check("метки источника, когда переданы",
          "utm_source=whatsapp&utm_medium=bot&utm_campaign=concierge" in с_метками, с_метками)
    check("без источника — без меток", "utm_" not in link, link)
    дети = booking_form_url("https://airisresidence.kz", room_slug="standart",
                            check_in="2026-10-20", check_out="2026-10-23", guests=2,
                            children_ages=[3, 5], today=сегодня)
    check("дети — возрастом через запятую", "children=3,5" in дети, дети)

    # Прошедшие и перепутанные даты в ссылку не кладём: форма открылась бы
    # на чужом периоде, а уже заполненное поле гость не перепроверит.
    прошлое = booking_form_url("https://airisresidence.kz", room_slug="comfort",
                               check_in="2026-10-01", check_out="2026-10-03", today=сегодня)
    check("прошедшую дату в ссылку не кладём", "date=" not in прошлое, прошлое)
    наоборот = booking_form_url("https://airisresidence.kz", room_slug="comfort",
                                check_in="2026-10-22", check_out="2026-10-20", today=сегодня)
    check("выезд раньше заезда — без дат", "date=" not in наоборот, наоборот)
    check("слишком долгий срок — без дат",
          stay_for_link("2026-10-20", "2026-12-20", сегодня)[0] is None)
    check("незнакомый язык не попадает в ссылку",
          "lang=" not in booking_form_url("https://airisresidence.kz", lang="de", today=сегодня))
    check("неизвестная категория не ломает ссылку",
          booking_form_url("https://airisresidence.kz", room_slug="нет-такого", today=сегодня)
          == "https://airisresidence.kz/booking")

    # Что ответ инструмента говорит модели: при подставленных датах —
    # что именно подставлено; без них — честное «выбери даты сам».
    from app.concierge import BOOKING_LINK_TOOL as _ССЫЛКА, ROOM_PAGE_TOOL as _СТРАНИЦА  # noqa: PLC0415
    from app.concierge import _tool_link as _ссылка  # noqa: PLC0415
    from app.config import Settings as _Set  # noqa: PLC0415

    факты = {"hotel": {"url": "https://airisresidence.kz"},
             "rooms": [{"slug": "comfort", "name": "Comfort", "url": "https://airisresidence.kz/nomera/comfort"}]}
    сказано = _ссылка(_Set(), факты, {"room": "comfort", "check_in": "2099-01-10",
                                          "check_out": "2099-01-12", "guests": 2, "lang": "kk"})
    check("модели сказано, что форма заполнена", "уже заполненной" in сказано, сказано[:160])
    check("ссылка бота с меткой WhatsApp", "utm_source=whatsapp" in сказано, сказано[:160])
    # Opus 5.5 на казахском дважды из двух прислал ссылку без вопроса об
    # имени: правило в своде проиграло, напоминание в ответе инструмента —
    # то место, которое модель читает перед ответом.
    check("вместе со ссылкой напомнить спросить имя", "на чьё имя будет бронь" in сказано)
    check("и названы подставленные даты", "10.01.2099" in сказано and "12.01.2099" in сказано)
    без_дат = _ссылка(_Set(), факты, {"room": "comfort", "guests": 2})
    check("без дат — предупреждение выбрать их в форме",
          "какие даты выбрать" in без_дат and "date=" not in без_дат, без_дат[:160])
    свойства = _ССЫЛКА["input_schema"]["properties"]
    check("инструмент ссылки принимает язык и детей",
          "lang" in свойства and "children_ages" in свойства)
    check("страница номера тоже открывается на языке гостя",
          "lang" in _СТРАНИЦА["input_schema"]["properties"])


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
        import app.webhooks_api as _wh

        # Приём уведомления теперь шлёт отелю сообщение в WhatsApp. Ключи в
        # .env боевые, и первый же прогон отправил три настоящих сообщения —
        # проверка не должна выходить наружу ни при каких обстоятельствах.
        отправлено_отелю: list[tuple[str, str]] = []

        async def _не_шлём(number: str, kind: str) -> None:
            отправлено_отелю.append((number, kind))

        настоящий = _wh.notify_hotel_booking
        _wh.notify_hotel_booking = _не_шлём

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
        check("событие разобрано и записано",
              len(first.json().get("saved") or []) == 1, first.text[:100])

        # Exely присылает уведомление снова, если мы ответили медленно.
        # Второй раз заводить бронь нельзя.
        again = client.post("/api/webhooks/exely", json=body, headers={"X-Api-Key": KEY})
        check("повтор не заводит второе событие", again.json().get("duplicates") == 1,
              again.text[:100])
        check("на повторе ничего не сохранено", not (again.json().get("saved") or []))

        # Настоящее тело Exely: список, тип с приставкой, номер во вложенном
        # payload. Именно на такой форме разбор молчал целый месяц.
        живое = [{"eventId": f"{ref}-live", "eventType": "webpms:create_booking",
                  "payload": {"BookingNumber": f"{ref}-L", "PropertyId": "509506"}}]
        как_у_exely = client.post("/api/webhooks/exely", json=живое,
                                  headers={"X-Api-Key": KEY})
        check("настоящее тело Exely принимается", как_у_exely.status_code == 200)
        check("из настоящего тела событие извлекается",
              len(как_у_exely.json().get("saved") or []) == 1, как_у_exely.text[:100])

        # Два события в одном запросе — обычное дело; потерять второе так же
        # легко, как раньше терялись все.
        пара = client.post("/api/webhooks/exely", headers={"X-Api-Key": KEY},
                           json=живое + [{"eventId": f"{ref}-2",
                                          "eventType": "webpms:cancel_booking",
                                          "payload": {"BookingNumber": f"{ref}-L"}}])
        check("второе событие в том же запросе не теряется",
              пара.json().get("events") == 2, пара.text[:100])
        check("создание и отмена одной брони — разные события",
              len(пара.json().get("saved") or []) == 1, пара.text[:100])

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
        # Отель узнаёт о новой броне только отсюда: платёж идёт между Exely
        # и банком, мимо нас. Если уведомление перестанет вызываться, никто
        # этого не заметит — заказчица просто снова спросит, как узнать об
        # оплате.
        check("о разобранной броне отель уведомляется",
              any(n.startswith(ref) for n, _ in отправлено_отелю),
              str(отправлено_отелю)[:120])
        check("на отмену тоже уведомляем",
              any("cancel" in k for _, k in отправлено_отелю),
              str([k for _, k in отправлено_отелю])[:120])
    finally:
        try:
            _wh.notify_hotel_booking = настоящий
        except NameError:
            pass
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
        "bin": "200640012670", "iik": "KZ11722S000048166255"}}}
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

    # Гость нажал «ответить» на сообщение бота и написал «На троих».
    # 2026-08-30, 19:51: WhatsApp прислал это типом `quotedMessage`, ветки для
    # него не было, текст остался пустым, вебхук отчитался «пустое сообщение»,
    # и человек прождал ответа три часа.
    #
    # Разбор «по типу сообщения» терял гостя уже второй раз — до этого на
    # голосовых. Список типов у мессенджера открытый, поэтому проверяем не
    # конкретный тип, а то, что текст находится в любом из контейнеров.
    def _incoming(kind: str, **md):
        return _parse({"typeWebhook": "incomingMessageReceived", "idMessage": "Q1",
                       "senderData": {"chatId": "77019300370@c.us", "senderName": "Гость"},
                       "messageData": {"typeMessage": kind, **md}})

    quoted = _incoming("quotedMessage",
                       extendedTextMessageData={"text": "На троих"},
                       quotedMessage={"typeMessage": "extendedTextMessage"})
    check("ответ с цитатой не теряется", quoted is not None and quoted.text == "На троих",
          repr(quoted.text if quoted else None))
    check("ответ с цитатой не считается файлом", quoted is not None and not quoted.has_file)

    unknown = _incoming("reactionMessage",
                        extendedTextMessageData={"text": "а можно раньше заехать?"})
    check("незнакомый тип с текстом не теряется",
          unknown is not None and unknown.text == "а можно раньше заехать?",
          repr(unknown.text if unknown else None))

    # Голосовое под незнакомым именем типа опознаётся по содержимому: сегодня
    # это audioMessage, завтра мессенджер назовёт его иначе.
    by_mime = _incoming("audioMessageNew",
                        fileMessageData={"downloadUrl": "https://x/v.opus",
                                         "mimeType": "audio/opus"})
    check("голосовое опознаётся по типу содержимого",
          by_mime is not None and by_mime.is_voice)
    check("у такого голосового есть имя для распознавания",
          by_mime is not None and by_mime.file_name.endswith(".oga"))

    with_caption = _incoming("imageMessage",
                             fileMessageData={"downloadUrl": "https://x/1.jpg",
                                              "fileName": "1.jpg", "caption": "это чек"})
    check("подпись к файлу по-прежнему читается",
          with_caption is not None and with_caption.text == "это чек")
    check("файл по-прежнему виден", with_caption is not None and with_caption.has_file)

    # Молчание должно быть решением, а не следствием незнакомого типа.
    # Реакция «палец вверх» на реплику консьержа — не вопрос, отвечать на неё
    # навязчиво. А геопозиция, визитка или тип, которого у мессенджера вчера
    # ещё не было, — это обращение, и оставлять его без ответа нельзя.
    reaction = _incoming("reactionMessage")
    check("реакция не читается и ответа не требует",
          reaction is not None and not reaction.readable and reaction.is_noise)
    for quiet in ("pollMessage", "pollUpdateMessage", "editedMessage", "deletedMessage"):
        item = _incoming(quiet)
        check(f"«{quiet}» — сознательное молчание", item is not None and item.is_noise)

    for speak in ("locationMessage", "contactMessage", "stickerMessage", "чегоНетВСписке"):
        item = _incoming(speak)
        check(f"«{speak}» без содержимого получит ответ, а не тишину",
              item is not None and not item.readable and not item.is_noise)

    check("тип сообщения доезжает до вебхука",
          _incoming("locationMessage").kind == "locationMessage")

    # Отель может писать заметки самому себе — WhatsApp это разрешает, и такие
    # заметки приходят обычным входящим. Отвечать на них значит засорять
    # личный блокнот владельца.
    own = "77066826635@c.us"
    self_note = _parse({
        "typeWebhook": "incomingMessageReceived", "idMessage": "S1",
        "instanceData": {"wid": own},
        "senderData": {"chatId": own, "senderName": "Отель"},
        "messageData": {"typeMessage": "textMessage",
                        "textMessageData": {"textMessage": "не забыть заказать полотенца"}},
    })
    check("заметка самому себе разбирается как обычное сообщение",
          self_note is not None and self_note.chat_id == own)
    check("текст ответа на нечитаемое зовёт написать текстом",
          "текстом" in UNREADABLE["ru"].lower())
    check("текст ответа говорит, чем можно помочь",
          "свободные номера" in UNREADABLE["ru"])

    # Заявки с сайта уходили только в Telegram, а он у отеля не настроен.
    # Шесть штук пролежали в базе непрочитанными, у четырёх дата заезда
    # успела пройти: гость заполнял форму и не получал звонка. Поломка
    # дорогая и при этом совершенно незаметная — ни ошибки, ни жалобы.
    from app.db import Lead as _Lead  # noqa: PLC0415
    from app.notify import lead_lines  # noqa: PLC0415

    sample = _Lead(id=7, name="Пётр", phone="+77010000000", email="p@example.kz",
                   check_in="2026-09-10", check_out="2026-09-12", adults=2,
                   room="comfort", comment="ранний заезд")
    note = "\n".join(lead_lines(sample))
    for нужно in ("Пётр", "+77010000000", "Comfort", "2026-09-10", "ранний заезд"):
        check(f"в уведомлении о заявке есть «{нужно}»", нужно in note)
    check("уведомление говорит, что делать", "Перезвоните" in note)

    from app.config import Settings as _S  # noqa: PLC0415

    # У отеля есть приложение Exely, и оно само присылает уведомление о
    # каждой броне и отмене. Заказчица прямо попросила не дублировать:
    # «зачем на ватсап приходит уведомление? у нас приложение есть».
    #
    # Второй канал об одном и том же приучает пролистывать сообщения не
    # читая — а вместе с ними и те, ради которых всё делалось. Поэтому по
    # умолчанию про брони молчим.
    check("про брони по умолчанию не пишем",
          not _S(notify_bookings="").notify_bookings)
    check("но включить обратно можно одной настройкой",
          bool(_S(notify_bookings="1").notify_bookings))
    # А это Exely не присылает никогда: заявку с сайта он не видит вовсе,
    # просьбу об отмене из переписки — тоже, и расчёт возврата не делает.
    check("заявка с сайта уходит независимо от настройки",
          "Перезвоните" in note)
    # Пустые поля не должны превращаться в «None»: заявку читает человек.
    bare = "\n".join(lead_lines(_Lead(id=8, name="Аноним", phone="+77010000001")))
    check("пустые поля заявки не показываются как None", "None" not in bare, bare[:80])
    check("незаполненная категория названа словами", "не выбран" in bare)

    # Получателей уведомлений может быть несколько: владелец и менеджер на
    # смене. Добавлять второго правкой кода неправильно, поэтому список.

    check("пусто — получателей нет, шлём на номер бота",
          _S(lead_notify_phone="").lead_notify_numbers == [])
    check("один номер разбирается",
          _S(lead_notify_phone="+7 701 930 0370").lead_notify_numbers == ["77019300370"])
    check("несколько номеров через запятую",
          len(_S(lead_notify_phone="77019300370, 77066826635").lead_notify_numbers) == 2)
    check("точка с запятой тоже разделяет",
          len(_S(lead_notify_phone="77019300370; 87775310009").lead_notify_numbers) == 2)
    check("повтор номера не удваивает отправку",
          len(_S(lead_notify_phone="77019300370, +7 701 930 0370").lead_notify_numbers) == 1)
    # Короткий номер — опечатка. Отправить по нему значит попасть в чужой чат.
    check("слишком короткий номер отбрасывается",
          _S(lead_notify_phone="123").lead_notify_numbers == [])

    # Exely присылает СПИСОК событий, а номер брони лежит во вложенном
    # payload под именем BookingNumber с большой буквы. Разбор ждал объект и
    # другие имена, поэтому за месяц накопилось 190 уведомлений, из которых
    # не извлечено НИЧЕГО: все с типом «unknown» и пустым номером. Гости не
    # получили ни подтверждений брони, ни сообщений об отмене, а отель не
    # узнал ни об одной новой броне.
    from app.webhooks_api import _events, _number  # noqa: PLC0415

    живое = [{"eventId": "f1a19d5a", "eventType": "webpms:create_booking",
              "creationTime": "2026-08-31T06:38:24.343Z",
              "payload": {"BookingNumber": "20260901-509506-1262595670",
                          "PropertyId": "509506"}}]
    события = _events(живое)
    check("список событий Exely разбирается", len(события) == 1, str(len(события)))
    check("номер брони достаётся из вложенного payload",
          _number(события[0]) == "20260901-509506-1262595670", _number(события[0]))

    # В одном запросе событий может быть несколько, и потерять второе так же
    # легко, как раньше терялись все.
    двойное = _events(живое + [{"eventId": "b2", "eventType": "webpms:cancel_booking",
                                "payload": {"BookingNumber": "X-2"}}])
    check("несколько событий в одном запросе не теряются", len(двойное) == 2)
    check("номер второго события тоже читается", _number(двойное[1]) == "X-2")

    # Одиночный объект и обёртка со списком внутри — тоже рабочие формы.
    check("одиночное событие разбирается", len(_events(живое[0])) == 1)
    check("обёртка со списком разбирается", len(_events({"events": живое})) == 1)
    check("мусор не роняет разбор", _events("не json") == [])

    # Приставка «webpms:» ничего не различает — все события приходят с ней, а
    # сопоставление с шаблонами сообщений идёт по «create_booking».
    class _Req:
        headers: dict = {}

    from app.webhooks_api import _kind  # noqa: PLC0415
    check("приставка Exely отбрасывается",
          _kind(события[0], _Req()) == "create_booking", _kind(события[0], _Req()))
    check("тип без приставки не ломается",
          _kind({"eventType": "bookingCreated"}, _Req()) == "bookingCreated")

    # Типы, которыми Exely называет события на самом деле. Пересчёт прошлых
    # уведомлений 2026-08-31 показал ровно четыре: create_booking (50),
    # cancel_booking (21), check_in (55), check_out (61).
    from app.guest_messages import EVENT_MESSAGES  # noqa: PLC0415

    check("создание брони сопоставлено с сообщением",
          bool(EVENT_MESSAGES.get("create_booking")))
    check("отмена брони сопоставлена с сообщением",
          bool(EVENT_MESSAGES.get("cancel_booking")))
    # Заезд и выезд гостю не пишем: он в этот момент стоит на стойке.
    check("на заезд и выезд сообщений нет",
          not EVENT_MESSAGES.get("check_in") and not EVENT_MESSAGES.get("check_out"))

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
          "текстом" in voice_reply.text.lower(), voice_reply.text[:60])
    check("голосовое не разбирается как платёжка",
          "платёжный документ" not in voice_reply.text)
    check("на голосовое снимки не прикладываются", not voice_reply.photos)

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

    # Живое голосовое от гостя 2026-08-29 в 23:20 получило в ответ «голосовые
    # пока не распознаю» — при том что распознавание было включено и
    # работало. В логах: файл скачался (200 OK), а служба ответила 400
    # «Unsupported file format oga». Формат она определяет ПО ИМЕНИ ФАЙЛА, а
    # WhatsApp называет голосовые `.oga`; внутри при этом обычный OGG,
    # который принимается под именем `.ogg`. Проверка на .wav этого не ловила
    # — расширение было своё, правильное.
    #
    # Поэтому имя, пришедшее от мессенджера, больше не используется: формат
    # берётся из первых байтов записи.
    from app.speech import _format as _fmt  # noqa: PLC0415

    check("OGG опознаётся по сигнатуре — это формат голосовых WhatsApp",
          _fmt(b"OggS" + bytes(20)) == ("ogg", "audio/ogg"))
    check("WAV опознаётся", _fmt(b"RIFF" + bytes(4) + b"WAVE" + bytes(8))[0] == "wav")
    check("MP3 с тегом опознаётся", _fmt(b"ID3" + bytes(20))[0] == "mp3")
    check("MP3 без тега опознаётся", _fmt(bytes([0xFF, 0xFB, 0x90]) + bytes(20))[0] == "mp3")
    check("M4A опознаётся по смещённой сигнатуре",
          _fmt(bytes(4) + b"ftyp" + bytes(12))[0] == "m4a")
    check("WEBM опознаётся", _fmt(bytes([0x1A, 0x45, 0xDF, 0xA3]) + bytes(20))[0] == "webm")
    # Незнакомая и пустая запись не должны ронять отправку: пусть служба сама
    # скажет, что не так, — это честнее, чем не отправить вовсе.
    check("незнакомая запись получает разумное имя", _fmt(b"zzzz" + bytes(20))[0] == "mp3")
    check("пустая запись не роняет определение", _fmt(b"")[0] == "mp3")
    check("расширение от мессенджера не используется",
          _fmt(b"OggS" + bytes(20))[0] != "oga")

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

    # Вызов инструмента — это ДВЕ записи: обращение консьержа и ответ на него.
    # Окно последних реплик режется по счёту и рано или поздно проходит между
    # ними. Тогда история открывается ответом инструмента, к которому нет
    # вопроса, модель отвечает 400, а гость получает «не смог обработать».
    #
    # Поймано на живом голосовом 2026-08-29: расшифровка сработала, ответа
    # гость не получил, и дело было не в голосе — разговор просто дорос до
    # длины, на которой окно разрезало пару. Чем дольше человек переписывается,
    # тем вероятнее он это поймает, а по симптому не догадаешься.
    for depth in range(1, 7):
        window = await load_history(SessionLocal, "whatsapp", CHAT, depth=depth)
        if not window:
            continue
        first, last = window[0], window[-1]
        opens_ok = first["role"] == "user" and not (
            isinstance(first["content"], list)
            and any(b.get("type") == "tool_result" for b in first["content"]
                    if isinstance(b, dict))
        )
        closes_ok = not (
            last["role"] == "assistant"
            and isinstance(last["content"], list)
            and any(b.get("type") == "tool_use" for b in last["content"]
                    if isinstance(b, dict))
        )
        check(f"глубина {depth}: история открывается репликой гостя", opens_ok,
              f"{first['role']}: {str(first['content'])[:60]}")
        check(f"глубина {depth}: история не обрывается на вызове инструмента", closes_ok,
              f"{last['role']}: {str(last['content'])[:60]}")
    check("история всегда начинается с гостя",
          not short or short[0]["role"] == "user", short[0]["role"] if short else "")

    check("чужая переписка не подмешивается",
          await load_history(SessionLocal, "whatsapp", "qa-другой@c.us") == [])

    check("новое сообщение не повтор", not await seen_before(SessionLocal, "whatsapp", "qa-m1"))
    check("то же сообщение — повтор", await seen_before(SessionLocal, "whatsapp", "qa-m1"))
    check("другое сообщение не повтор", not await seen_before(SessionLocal, "whatsapp", "qa-m2"))
    check("пустой идентификатор не считается", not await seen_before(SessionLocal, "whatsapp", ""))

    await wipe()


async def qa_corporate() -> None:
    """Корпоративный кабинет: от заведения компании до брони сотрудником.

    Раздел появился позже остальных, и до него на кабинет не было ни одной
    проверки — при том, что это отдельный продукт, который показывают
    компаниям. Ломается он тихо: страницы открываются, вход работает, а
    договорная цена не применяется, и сотрудник видит обычный прайс.
    Заметят это на счёте, то есть поздно.

    Всё идёт по HTTP, а не вызовом функций: половина смысла кабинета — в
    доступах и схемах запроса, а они живут именно на этом слое. Проверка
    убирает за собой и потому переживает повторный запуск.
    """
    head("Корпоративный кабинет")

    from httpx import ASGITransport  # noqa: PLC0415 — нужен только здесь
    from sqlalchemy import delete, select  # noqa: PLC0415

    from app.db import (  # noqa: PLC0415
        Company,
        CompanyRate,
        CompanyUser,
        CorpBooking,
        Room,
    )
    from app.config import get_settings  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    settings = get_settings()

    SLUG = "qa-korp-proverka"
    MAIL = "qa-korp@example.invalid"
    PASS = "qa-parol-sotrudnika-1"

    async def wipe_corp() -> None:
        async with SessionLocal() as ses:
            found = (
                await ses.execute(select(Company).where(Company.slug == SLUG))
            ).scalar_one_or_none()
            if found is None:
                return
            await ses.execute(delete(CorpBooking).where(CorpBooking.company_id == found.id))
            await ses.execute(delete(CompanyRate).where(CompanyRate.company_id == found.id))
            await ses.execute(delete(CompanyUser).where(CompanyUser.company_id == found.id))
            await ses.execute(delete(Company).where(Company.id == found.id))
            await ses.commit()

    await wipe_corp()
    try:
        async with SessionLocal() as ses:
            room = (
                await ses.execute(select(Room).where(Room.is_published.is_(True)).limit(1))
            ).scalar_one_or_none()
        if room is None:
            check("есть опубликованный номер для проверки", False, "в базе нет номеров")
            return
        slug, public = room.slug, room.price

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://qa") as hotel:
            answer = await hotel.post(
                "/api/auth/login",
                json={"username": settings.admin_username, "password": settings.admin_password},
            )
            body = answer.json() if answer.status_code == 200 else {}
            token = body.get("token") or body.get("accessToken") or body.get("access_token")
            check("отель входит в админку", bool(token), f"HTTP {answer.status_code}")
            if not token:
                return
            head_auth = {"Authorization": f"Bearer {token}"}

            made = await hotel.post(
                "/api/admin/corp/companies",
                headers=head_auth,
                json={
                    "slug": SLUG,
                    "name": "ТОО Проверка",
                    "discountPercent": 15,
                    "contactName": "И",
                    "contactPhone": "+77000000000",
                    "contactEmail": "qa@example.invalid",
                },
            )
            check("компания заводится", made.status_code == 201,
                  f"HTTP {made.status_code} {made.text[:80]}")

            # Договорная цена за конкретную категорию — то, ради чего кабинет и
            # существует. Ставим заведомо ниже прайса, чтобы подмена была видна,
            # а не совпала со скидкой случайно.
            deal = max(100, public // 2 // 100 * 100)
            rates = await hotel.put(
                f"/api/admin/corp/companies/{SLUG}/rates",
                headers=head_auth,
                json=[{"roomSlug": slug, "price": deal}],
            )
            check("договорные цены сохраняются", rates.status_code == 200,
                  f"HTTP {rates.status_code} {rates.text[:80]}")

            staff_made = await hotel.post(
                f"/api/admin/corp/companies/{SLUG}/users",
                headers=head_auth,
                json={
                    "email": MAIL,
                    "fullName": "Бухгалтер",
                    "phone": "+77001112233",
                    "role": "admin",
                    "password": PASS,
                },
            )
            check("первый сотрудник заводится отелем", staff_made.status_code == 201,
                  f"HTTP {staff_made.status_code} {staff_made.text[:80]}")

            booking: dict = {}
            # Отдельный клиент: у сотрудника компании свои доступы, и одалживать
            # ему админский токен нельзя — иначе проверка докажет только то, что
            # работает админка.
            async with httpx.AsyncClient(transport=transport, base_url="http://qa") as staff:
                entered = await staff.post(
                    "/api/corp/login", json={"email": MAIL, "password": PASS}
                )
                check("сотрудник входит в кабинет", entered.status_code == 200,
                      f"HTTP {entered.status_code}")
                sj = entered.json() if entered.status_code == 200 else {}
                stoken = sj.get("token") or sj.get("accessToken") or sj.get("access_token")
                staff_auth = {"Authorization": f"Bearer {stoken}"}

                wrong = await staff.post(
                    "/api/corp/login", json={"email": MAIL, "password": "неверный"}
                )
                check("с неверным паролем в кабинет не пускают", wrong.status_code >= 400,
                      f"HTTP {wrong.status_code}")

                listing = await staff.get("/api/corp/rooms", headers=staff_auth)
                rooms = listing.json() if listing.status_code == 200 else []
                mine = next((x for x in rooms if x.get("slug") == slug), None)
                check("номера отдаются сотруднику", mine is not None, f"HTTP {listing.status_code}")
                if mine:
                    check("договорная цена применилась", mine.get("corpPrice") == deal,
                          f"{mine.get('corpPrice')} вместо {deal}")
                    # Публичная цена рядом — нарочно: сотрудник должен видеть,
                    # что через кабинет дешевле, иначе уйдёт на агрегатор.
                    check("прайс показан рядом для сравнения",
                          mine.get("publicPrice") == public, str(mine.get("publicPrice")))

                closed = await staff.get("/api/corp/rooms")
                check("без входа кабинет закрыт", closed.status_code >= 400,
                      f"HTTP {closed.status_code}")

                check_in = (hotel_today() + timedelta(days=10)).isoformat()
                check_out = (hotel_today() + timedelta(days=12)).isoformat()
                created = await staff.post(
                    "/api/corp/bookings",
                    headers=staff_auth,
                    json={
                        "checkIn": check_in,
                        "checkOut": check_out,
                        "comment": "проверка",
                        "items": [{"roomSlug": slug, "guestName": "Петров П.", "guests": 1}],
                    },
                )
                check("сотрудник оформляет бронь", created.status_code == 201,
                      f"HTTP {created.status_code} {created.text[:80]}")
                booking = created.json() if created.status_code == 201 else {}
                check("две ночи посчитаны по договорной цене",
                      booking.get("totalAmount") == deal * 2,
                      f"{booking.get('totalAmount')} вместо {deal * 2}")
                check("номер брони присвоен", bool(booking.get("number")),
                      str(booking.get("number")))

                own = await staff.get("/api/corp/bookings", headers=staff_auth)
                check("бронь видна сотруднику",
                      own.status_code == 200 and len(own.json() or []) == 1,
                      f"HTTP {own.status_code}")

            seen = await hotel.get("/api/admin/corp/bookings", headers=head_auth)
            ours = [b for b in (seen.json() or []) if b.get("number") == booking.get("number")]
            check("бронь видна отелю", bool(ours), f"HTTP {seen.status_code}")
    finally:
        await wipe_corp()


async def qa_followup() -> None:
    """Дожим оборванных разговоров.

    Обращение к модели здесь не проверяется — оно стоит денег и отвечает
    каждый раз по-разному. Проверяется всё, что вокруг: кого вообще берём в
    работу, сколько раз можно написать и когда счёт обнуляется. Ошибка в этой
    арифметике не падает, а тихо превращается в рассылку — гость получает
    третье и четвёртое напоминание, и номер отеля улетает в блокировку.
    """
    head("Дожим оборванных разговоров")

    import json  # noqa: PLC0415
    from datetime import timezone as _tz  # noqa: PLC0415

    from sqlalchemy import delete as _delete  # noqa: PLC0415

    from app.db import DialogFollowup, DialogMessage  # noqa: PLC0415
    from app.followup import (  # noqa: PLC0415
        DECIDE_PROMPT,
        FINAL_HOURS,
        MAX_AGE_HOURS,
        MAX_STEPS,
        STALE_HOURS,
        _stale_chats,
        _step_for,
        _text_of,
        _who,
    )

    check("номер в логе скрыт до последних цифр", _who("77054004448@c.us") == "…4448",
          _who("77054004448@c.us"))
    check("чат без цифр не роняет опознание", bool(_who("@g.us")))

    # В историю ложатся и вызовы инструментов. Для решения важно то, что
    # консьерж сказал ГОСТЮ, — иначе модель увидит служебный JSON вместо
    # разговора и решит по нему.
    tool_call = json.dumps(
        [{"type": "text", "text": "Свободен Comfort"},
         {"type": "tool_use", "name": "check_availability", "input": {}}],
        ensure_ascii=False,
    )
    check("из служебной записи достаётся сказанное гостю",
          _text_of(tool_call) == "Свободен Comfort", _text_of(tool_call))
    check("обычная реплика не искажается", _text_of("Добрый день") == "Добрый день")
    check("нечитаемая запись не роняет разбор", _text_of("[не json") == "[не json")

    CHAT = "qa-followup-77000000000@c.us"

    async def wipe_followup() -> None:
        async with SessionLocal() as ses:
            await ses.execute(_delete(DialogFollowup).where(DialogFollowup.chat_id == CHAT))
            await ses.execute(_delete(DialogMessage).where(DialogMessage.chat_id == CHAT))
            await ses.commit()

    async def say(role: str, text: str, hours_ago: float) -> None:
        async with SessionLocal() as ses:
            ses.add(DialogMessage(
                channel="whatsapp", chat_id=CHAT, role=role, content=text,
                created_at=datetime.now(_tz.utc) - timedelta(hours=hours_ago),
            ))
            await ses.commit()

    async def mark(step: int, hours_ago: float) -> None:
        async with SessionLocal() as ses:
            ses.add(DialogFollowup(
                channel="whatsapp", chat_id=CHAT, step=step,
                sent_at=datetime.now(_tz.utc) - timedelta(hours=hours_ago),
            ))
            await ses.commit()

    await wipe_followup()
    try:
        # Свежий разговор трогать рано: гость мог отойти на десять минут.
        await say("user", "есть номера?", 1.2)
        await say("assistant", "Свободен Comfort, 45 000 ₸", 1.0)
        async with SessionLocal() as ses:
            chats = {c for c, _ in await _stale_chats(ses, 500)}
            check("свежий разговор не дожимают", CHAT not in chats)

        # Прошло достаточно — берём в работу.
        await wipe_followup()
        await say("user", "есть номера?", STALE_HOURS + 1.5)
        await say("assistant", "Свободен Comfort, 45 000 ₸", STALE_HOURS + 1.0)
        async with SessionLocal() as ses:
            chats = {c for c, _ in await _stale_chats(ses, 500)}
            check("замолчавший разговор берётся в работу", CHAT in chats)
            check("первое сообщение — шаг 1", await _step_for(ses, CHAT) == 1,
                  str(await _step_for(ses, CHAT)))

        # Последним говорил гость — значит ждём ответа консьержа, а не дожима.
        await say("user", "а сколько всего?", STALE_HOURS + 0.5)
        async with SessionLocal() as ses:
            chats = {c for c, _ in await _stale_chats(ses, 500)}
            check("если последним писал гость, дожима нет", CHAT not in chats)

        # Слишком старый разговор закрыт навсегда: напоминание через неделю —
        # это рассылка, а не забота.
        await wipe_followup()
        await say("user", "есть номера?", MAX_AGE_HOURS + 10)
        await say("assistant", "Свободен Comfort", MAX_AGE_HOURS + 5)
        async with SessionLocal() as ses:
            chats = {c for c, _ in await _stale_chats(ses, 500)}
            check("давно заброшенный разговор не трогают", CHAT not in chats)

        # Счёт шагов и пауза между ними.
        await wipe_followup()
        await say("user", "есть номера?", 30)
        await say("assistant", "Свободен Comfort", 29)
        await mark(1, 1)
        async with SessionLocal() as ses:
            check("сразу после первого второго не шлём", await _step_for(ses, CHAT) is None)

        await wipe_followup()
        await say("user", "есть номера?", 60)
        await say("assistant", "Свободен Comfort", 59)
        await mark(1, FINAL_HOURS + 1)
        async with SessionLocal() as ses:
            check("через сутки уместно прощальное", await _step_for(ses, CHAT) == MAX_STEPS,
                  str(await _step_for(ses, CHAT)))

        await mark(2, 0.5)
        async with SessionLocal() as ses:
            check("третьего сообщения не бывает", await _step_for(ses, CHAT) is None)

        # Гость ответил — разговор живой, и всё начинается заново. Считаются
        # только отметки после его последней реплики, поэтому отдельного
        # сброса нет и забыть его негде.
        await say("user", "извините, отвлёкся", 0.2)
        async with SessionLocal() as ses:
            check("реплика гостя обнуляет счёт", await _step_for(ses, CHAT) == 1,
                  str(await _step_for(ses, CHAT)))

        await wipe_followup()
        async with SessionLocal() as ses:
            check("без реплик гостя дожимать нечего", await _step_for(ses, CHAT) is None)

        # Живая проверка на боевой переписке показала два вранья, оба опасные:
        # «номер всё ещё зарезервирован» (отель ничего не держит до оформления)
        # и попытка назвать цену заново, не проверив её.
        check("о наличии в настоящем времени говорить нельзя",
              "Ничего не говори о наличии В НАСТОЯЩЕМ ВРЕМЕНИ" in DECIDE_PROMPT)
        # Перечень нужен целиком: запрет «зарезервирован» модель обошла
        # словами «всё ещё доступен» — то же обещание, просто иначе сказанное.
        for word in ("«зарезервирован»", "«отложен»", "«пока свободен»",
                     "«всё ещё доступен»", "«номер за вами»"):
            check(f"названо запрещённое {word}", word in DECIDE_PROMPT)
        check("о наличии говорят в прошедшем времени",
              "только в прошедшем времени" in DECIDE_PROMPT)
        check("вместо обещания предлагают проверить заново",
              "посмотреть, свободно ли ещё?" in DECIDE_PROMPT)
        check("сообщение заканчивается закрытым вопросом",
              "ответ «да» или «нет»" in DECIDE_PROMPT)
        check("жалобу дожимать нельзя", "злится или жалуется" in DECIDE_PROMPT)
        check("отказавшегося не дожимают", "спасибо, не надо" in DECIDE_PROMPT)

        # Ушедший дожим должен лечь в историю наравне с обычным ответом.
        # Иначе получается разговор, где консьерж не помнит собственных слов:
        # гость отвечает «на троих» на вопрос ИЗ ДОЖИМА, а в истории этого
        # вопроса нет — и консьерж переспрашивает то, что сам же спросил час
        # назад. Ровно это и увидел живой гость 2026-08-30.
        import app.followup as _fu  # noqa: PLC0415
        from app.config import Settings as _Settings  # noqa: PLC0415

        sent_texts: list[str] = []

        class _Stub:
            def __init__(self, *a, **k) -> None:  # noqa: D107
                pass

            async def send(self, chat_id: str, text: str) -> str:
                sent_texts.append(text)
                return "stub"

        await wipe_followup()
        await say("user", "а есть Comfort на выходные?", 5)
        await say("assistant", "Свободен Comfort, 45 000 ₸ за ночь", 4)

        # Ночью рассылка отказывается работать — это правильно, но проверять
        # запись в историю приходится в любой час.
        real_channel, real_plan = _fu.WhatsAppChannel, _fu.plan
        real_quiet = _fu.quiet_hours

        async def _one_nudge(session, settings):  # noqa: ANN001
            return [_fu.Nudge(chat_id=CHAT, text="Мы смотрели Comfort. Забронируем?",
                              step=1, reason="проверка")]

        _fu.WhatsAppChannel, _fu.plan = _Stub, _one_nudge
        _fu.quiet_hours = lambda *a, **k: False
        try:
            async with SessionLocal() as ses:
                result = await _fu.run(ses, _Settings(followup_since="2020-01-01"), dry_run=False)
        finally:
            _fu.WhatsAppChannel, _fu.plan = real_channel, real_plan
            _fu.quiet_hours = real_quiet

        check("дожим отправлен", result.get("sent") == 1, str(result))
        check("текст ушёл гостю", sent_texts and "Забронируем?" in sent_texts[0])

        after = await load_history(SessionLocal, "whatsapp", CHAT, depth=12)
        check("дожим лёг в историю разговора",
              any(m["role"] == "assistant" and "Забронируем?" in str(m["content"])
                  for m in after),
              f"реплик в истории: {len(after)}")
        # Раз консьерж говорил последним, следующий дожим ждёт своей паузы, а
        # не уходит вдогонку сразу.
        async with SessionLocal() as ses:
            check("сразу второй дожим не уходит", await _step_for(ses, CHAT) is None)

        # Тормошить гостя дольше, чем помнишь его, нельзя. Дожим возвращается
        # к разговору до MAX_AGE_HOURS, а консьерж помнит разговор
        # CONTINUES_FOR — если второе меньше первого, бот сам продолжает
        # переписку и тут же переспрашивает даты, которые в ней уже названы.
        # Ровно это увидела гостья 2026-08-30.
        from app.dialogs import CONTINUES_FOR  # noqa: PLC0415

        check("память консьержа не короче горизонта дожима",
              CONTINUES_FOR.total_seconds() >= MAX_AGE_HOURS * 3600,
              f"помним {CONTINUES_FOR.total_seconds() / 3600:.0f} ч, "
              f"дожимаем до {MAX_AGE_HOURS} ч")
    finally:
        await wipe_followup()


async def qa_funnel() -> None:
    """Воронка и граница включения дожима.

    Граница проверяется здесь же, а не в разделе дожима, потому что защищает
    она ровно от того, что воронка показывает: в базе лежат прошлые
    переписки, и запуск без границы написал бы всем сразу — тестовым чатам,
    разговорам недельной давности, людям, давно всё решившим. Одна аккуратная
    функция мгновенно стала бы рассылкой.
    """
    head("Воронка и включение дожима")

    import json  # noqa: PLC0415
    from datetime import timezone as _tz  # noqa: PLC0415

    from sqlalchemy import delete as _delete  # noqa: PLC0415

    from app.config import Settings  # noqa: PLC0415
    from app.db import DialogFollowup, DialogMessage  # noqa: PLC0415
    from app.followup import _stale_chats  # noqa: PLC0415
    from app.funnel import _tool_names, collect, summarize  # noqa: PLC0415

    # ── Граница включения ────────────────────────────────────────────────
    # Пустая настройка означает «не дожимать», а не «дожимать всех подряд»:
    # рассылка гостям не должна включаться сама собой от выкладки кода.
    check("без даты включения дожим выключен",
          Settings(followup_since="").followup_from is None)
    check("мусор вместо даты не включает дожим",
          Settings(followup_since="позавчера").followup_from is None)
    check("дата разбирается", Settings(followup_since="2026-08-30").followup_from is not None)
    check("дата со временем разбирается",
          str(Settings(followup_since="2026-08-30T09:30").followup_from).startswith("2026-08-30 09:30"))
    # Человек пишет местное время, а в базе лежит UTC — без пояса сравнение
    # уехало бы на пять часов.
    check("дата без пояса считается алматинской",
          "+05:00" in str(Settings(followup_since="2026-08-30").followup_from))

    CHAT = "qa-funnel-77000000000@c.us"

    async def wipe() -> None:
        async with SessionLocal() as ses:
            await ses.execute(_delete(DialogFollowup).where(DialogFollowup.chat_id == CHAT))
            await ses.execute(_delete(DialogMessage).where(DialogMessage.chat_id == CHAT))
            await ses.commit()

    async def say(role: str, text: str, hours_ago: float) -> None:
        async with SessionLocal() as ses:
            ses.add(DialogMessage(
                channel="whatsapp", chat_id=CHAT, role=role, content=text,
                created_at=datetime.now(_tz.utc) - timedelta(hours=hours_ago),
            ))
            await ses.commit()

    def tool(name: str) -> str:
        return json.dumps([{"type": "tool_use", "id": "t1", "name": name, "input": {}}],
                          ensure_ascii=False)

    await wipe()
    try:
        # Разговор старше границы включения не берётся в работу, хотя по
        # тишине подходит. Это и есть защита тестовых переписок.
        await say("user", "есть номера?", 5)
        await say("assistant", "Свободен Comfort", 4)
        async with SessionLocal() as ses:
            after = datetime.now(_tz.utc) - timedelta(hours=1)
            before = datetime.now(_tz.utc) - timedelta(hours=48)
            late = {c for c, _ in await _stale_chats(ses, 500, since=after)}
            early = {c for c, _ in await _stale_chats(ses, 500, since=before)}
        check("разговор до даты включения не дожимают", CHAT not in late)
        check("разговор после даты включения дожимают", CHAT in early)

        # ── Стадии воронки ───────────────────────────────────────────────
        check("вызов инструмента опознаётся",
              _tool_names(tool("check_availability")) == {"check_availability"})
        check("обычная реплика инструментом не считается", _tool_names("Добрый день") == set())
        check("нечитаемая запись не роняет разбор", _tool_names("[сломано") == set())

        await wipe()
        await say("user", "есть номера?", 3)
        async with SessionLocal() as ses:
            talks = [t for t in await collect(ses, 30) if t.chat_id == CHAT]
        check("разговор без инструментов — «просто написал»",
              talks and talks[0].stage == "просто написал",
              talks[0].stage if talks else "не найден")

        await say("assistant", tool("check_availability"), 2.9)
        await say("assistant", "Свободен Comfort, 45 000 ₸", 2.8)
        async with SessionLocal() as ses:
            talks = [t for t in await collect(ses, 30) if t.chat_id == CHAT]
        check("после проверки наличия — «показали цены»",
              talks[0].stage == "показали цены", talks[0].stage)
        # Служебные записи гость не видел: считая их сообщениями, один вопрос
        # превращается в переписку из пяти реплик.
        check("вызовы инструментов не идут в счёт сообщений",
              talks[0].messages == 2, str(talks[0].messages))

        await say("assistant", tool("booking_link"), 2.5)
        async with SessionLocal() as ses:
            talks = [t for t in await collect(ses, 30) if t.chat_id == CHAT]
        check("после ссылки — «довели до формы»",
              talks[0].stage == "довели до формы", talks[0].stage)
        check("стадия — максимум, а не последнее действие", talks[0].saw_prices)
        check("молчание после ответа консьержа видно",
              talks[0].outcome == "молчит", talks[0].outcome)

        # Гость написал последним — это единственное, что требует действия
        # прямо сейчас, и путать его с молчанием нельзя.
        await say("user", "а завтрак входит?", 0.1)
        async with SessionLocal() as ses:
            talks = [t for t in await collect(ses, 30) if t.chat_id == CHAT]
        check("неотвеченный гость помечен «ждёт ответа»",
              talks[0].outcome == "ждёт ответа", talks[0].outcome)

        # ── Свод ─────────────────────────────────────────────────────────
        async with SessionLocal() as ses:
            total = summarize(await collect(ses, 30))
        check("этапы вложены друг в друга",
              total["этапы"][0]["сколько"] >= total["этапы"][1]["сколько"] >= total["этапы"][2]["сколько"],
              str([s["сколько"] for s in total["этапы"]]))
        check("первый этап всегда 100 %", total["этапы"][0]["доля"] == 100)
        check("пустая воронка не делит на ноль",
              summarize([])["этапы"][0]["доля"] == 100)
        check("пустая воронка не падает", summarize([])["разговоров"] == 0)
    finally:
        await wipe()


async def qa_refunds() -> None:
    """Возврат денег при отмене брони.

    Единственное место в проекте, где двигаются чужие деньги. Ошибка здесь
    не выглядит как «гость не получил ответа» — она выглядит как недостача,
    и обнаружится нескоро. Поэтому проверяется не только «вернули сколько
    надо», но и каждый случай, когда возвращать НЕЛЬЗЯ.

    Сеть не задействована: расчёт вынесен в отдельную функцию именно для
    того, чтобы его можно было проверить без банка и без Exely.
    """
    head("Возврат при отмене брони")

    from app.config import Settings as _S  # noqa: PLC0415
    from app.refunds import RefundPlan, describe, execute, plan_refund  # noqa: PLC0415
    from app.payments import get_provider as _get_provider  # noqa: PLC0415

    оплачен = {"pg_payment_id": "QA0000000000", "pg_amount": "50000",
               "pg_card_pan": "555555******4444"}

    # ── Банк подменяется на весь раздел ────────────────────────────────
    #
    # Здесь проверяются предохранители перед отправкой денег, и часть
    # проверок обязана дойти до самой отправки — иначе они ничего не
    # проверяют. Но `Settings()` читает `backend/.env`, где лежат
    # НАСТОЯЩИЕ ключи FreedomPay, и «отправка» получалась настоящей.
    #
    # Так и случилось 2026-09-01: прогон отправил в банк реальный запрос
    # на возврат 50 000 ₸ по реальному платежу. Банк его отклонил — сумма
    # больше оплаченного, — и деньги уцелели по случайности, а не по
    # замыслу. Полдня после этого ушло на выяснение у Exely и FreedomPay,
    # кто отправил возврат, которого никто не отправлял.
    #
    # Поэтому здесь не «постараемся не дойти до банка», а «дойти нельзя»:
    # провайдер подменён на записывающий стенд. Пустые ключи он по-прежнему
    # отражает как отсутствие доступа — иначе проверка «без доступа к
    # банку» потеряет смысл.
    import app.refunds as _ref  # noqa: PLC0415

    отправлено: list[dict] = []

    class _СтендБанка:
        name = "qa-stub"

        async def refund(self, **kwargs) -> dict:
            отправлено.append(kwargs)
            return {"message": "принят стендом"}

    def _стенд(settings):  # noqa: ANN001
        if not getattr(settings, "payment_provider", ""):
            return None
        return _СтендБанка()

    настоящий_провайдер = _ref.get_provider
    _ref.get_provider = _стенд
    try:
        await _qa_refunds_body(оплачен, отправлено)
    finally:
        _ref.get_provider = настоящий_провайдер

    # Список обязан быть НЕпустым: часть проверок по замыслу доходит до
    # самой отправки, и именно поэтому раньше они уходили в настоящий банк.
    # Пустой список означал бы, что проверка предохранителей ничего не
    # проверяет, а «до банка не дошли» выполняется само собой.
    check("проверки действительно доходят до отправки", len(отправлено) > 0,
          str(len(отправлено)))
    check("но уходят на стенд, а не в банк",
          all(str(k.get("payment_id", "")).startswith("QA") for k in отправлено),
          str([k.get("payment_id") for k in отправлено]))


async def _qa_refunds_body(оплачен: dict, отправлено: list) -> None:
    """Тело проверок возврата. Вынесено, чтобы банк был подменён целиком."""
    from app.config import Settings as _S  # noqa: PLC0415
    from app.refunds import RefundPlan, describe, execute, plan_refund  # noqa: PLC0415
    from app.payments import get_provider as _get_provider  # noqa: PLC0415

    def бронь(**поля):
        основа = {
            "number": "QA-BRON-NE-SUSHESTVUET",
            "status": "Cancelled",
            "guaranteeInfo": {"totalPrepaid": 50000.0},
            "cancellation": {"penaltyAmount": 0.0},
        }
        основа.update(поля)
        return основа

    # ── Обычный случай: ранняя отмена, штрафа нет ──────────────────────
    plan = plan_refund(бронь(), оплачен)
    check("возврат считается как предоплата минус штраф", plan.amount == 50000,
          str(plan.amount))
    check("платёж подхвачен", plan.payment_id == "QA0000000000")
    check("возврат признан положенным", plan.due, plan.problem)

    # ── Сумму считает Exely, а не мы ───────────────────────────────────
    # Правила отмены живут в Exely, там их меняет отель. Продублировать их
    # здесь значило бы однажды вернуть не ту сумму.
    частично = plan_refund(
        бронь(cancellation={"penaltyAmount": 20000.0}), оплачен)
    check("удержанный штраф вычитается", частично.amount == 30000, str(частично.amount))

    полностью = plan_refund(
        бронь(cancellation={"penaltyAmount": 50000.0}), оплачен)
    check("при полном удержании возвращать нечего", полностью.amount == 0)
    check("и это сказано словами",
          "удержано полностью" in полностью.problem, полностью.problem)
    check("такой план не считается положенным", not полностью.due)

    # ── Случаи, когда трогать деньги нельзя ────────────────────────────
    живая = plan_refund(бронь(status="Active"), оплачен)
    check("по неотменённой броне возврата нет", not живая.due, живая.problem)
    check("причина названа", "не отменена" in живая.problem)

    без_оплаты = plan_refund(бронь(guaranteeInfo={}), оплачен)
    check("без предоплаты возвращать нечего", not без_оплаты.due)
    check("причина названа", "предоплаты не было" in без_оплаты.problem)

    без_платежа = plan_refund(бронь(), {})
    check("без найденного платежа возврат не оформляется", not без_платежа.due)
    check("причина названа", "не найден" in без_платежа.problem, без_платежа.problem)

    # Повторный возврат — это вторая выдача тех же денег. Ошибиться в
    # сторону «не вернули» мягче: это заметят и исправят, а лишний возврат
    # всплывёт при сверке, когда деньги уже ушли.
    уже = plan_refund(бронь(), {**оплачен, "pg_refund_amount": "50000"})
    check("дважды один возврат не оформляется", not уже.due)
    check("сказано, что возврат уже был", "уже оформлен" in уже.problem, уже.problem)

    больше = plan_refund(
        бронь(guaranteeInfo={"totalPrepaid": 90000.0}), оплачен)
    check("нельзя вернуть больше оплаченного", not больше.due, больше.problem)

    # Мусор в данных не должен превращаться в перевод денег.
    кривая = plan_refund(
        бронь(guaranteeInfo={"totalPrepaid": "не число"}), оплачен)
    check("нечитаемая сумма не роняет расчёт", not кривая.due, кривая.problem)

    # ── Предохранители перед отправкой ─────────────────────────────────
    готовый = plan_refund(бронь(), оплачен)

    done, note = await execute(_S(refund_auto=False), готовый)
    check("по умолчанию деньги сами не уходят", not done, note)
    check("причина названа", "выключен" in note, note)

    done, note = await execute(_S(refund_auto=True, refund_max=10000), готовый)
    check("сумма выше предела требует человека", not done, note)
    check("предел назван в ответе", "предела" in note, note)

    # Предел защищает не от отеля, а от опечатки в правилах Exely: одна
    # лишняя цифра не должна уйти в банк без человеческого взгляда.
    нечего = RefundPlan(booking="X", problem="удержано полностью")
    done, note = await execute(_S(refund_auto=True), нечего)
    check("пустой план не отправляется", not done, note)

    # Отмена — не окончательное состояние. Из инструкции Exely (kb282396):
    # «Если в полученном письме гость подтвердит проживание, бронирование
    # будет автоматически восстановлено». Между расчётом и отправкой бронь
    # успевает ожить, а деньги обратно не позовёшь — поэтому статус
    # перечитывается перед самой отправкой.
    import app.refunds as _ref  # noqa: PLC0415

    настоящая = _ref._still_cancelled

    async def _ожила(settings, number):  # noqa: ANN001
        return False

    async def _не_проверить(settings, number):  # noqa: ANN001
        return None

    _ref._still_cancelled = _ожила
    try:
        done, note = await execute(_S(refund_auto=True, refund_max=0), готовый)
    finally:
        _ref._still_cancelled = настоящая
    check("по восстановленной броне деньги не уходят", not done, note)
    check("причина названа прямо", "восстановлена" in note, note)

    # Не удалось проверить — не повод считать, что всё в порядке, но и не
    # повод падать: дальше сработают остальные предохранители.
    _ref._still_cancelled = _не_проверить
    try:
        done, note = await execute(_S(refund_auto=True, refund_max=0), готовый)
    finally:
        _ref._still_cancelled = настоящая
    check("непроверенный статус не роняет отправку", isinstance(note, str), note)

    # Без ключей банка отправлять некуда, но и падать нельзя.
    #
    # Пустые значения задаются ЯВНО: настройки читают backend/.env, а там
    # теперь лежат настоящие ключи FreedomPay. Без этого «без доступа к
    # банку» перестаёт быть «без доступа», и проверка молча меняет смысл —
    # именно так она и упала, когда ключи появились.
    без_банка = _S(refund_auto=True, refund_max=0, payment_provider="",
                   payment_terminal_id="", payment_client_secret="")
    done, note = await execute(без_банка, готовый)
    check("без доступа к банку возврат не уходит", not done, note)
    check("причина понятна", "не настроен" in note, note)

    # ── Ключ повтора: защита от двойного возврата на стороне банка ─────
    # Сверено с документацией FreedomPay: у revoke.php есть необязательный
    # pg_idempotency_key. С ним банк сам отклонит второй такой же возврат,
    # даже если мы отправим его дважды — при обрыве связи, при повторном
    # уведомлении об отмене, при ручном запуске поверх автоматического. Своя
    # защита смотрит на данные, которые могли устареть; эта надёжнее.
    отправлено: dict = {}

    class _Банк:
        name = "freedompay"

        async def refund(self, **kw):  # noqa: ANN003
            отправлено.update(kw)
            return {"message": "принят"}

    настоящий_провайдер = _ref.get_provider
    настоящая_проверка = _ref._still_cancelled

    async def _отменена(settings, number):  # noqa: ANN001
        return True

    _ref.get_provider = lambda s: _Банк()
    _ref._still_cancelled = _отменена
    try:
        план = RefundPlan(booking="QA-IDEMP-1", prepaid=50000, penalty=20000,
                          amount=30000, payment_id="QA0000000000")
        done, note = await execute(_S(refund_auto=True, refund_max=0), план)
    finally:
        _ref.get_provider = настоящий_провайдер
        _ref._still_cancelled = настоящая_проверка

    check("возврат уходит в банк", done, note)
    check("сумма передана верно", отправлено.get("amount_tenge") == 30000,
          str(отправлено.get("amount_tenge")))
    check("ключ повтора передан", bool(отправлено.get("idempotency")))
    check("ключ повтора привязан к броне",
          "QA-IDEMP-1" in str(отправлено.get("idempotency")),
          str(отправлено.get("idempotency")))
    # Сумма в ключе тоже нужна: частичный возврат поверх полного — другая
    # операция, и блокировать её этим ключом нельзя.
    check("ключ повтора учитывает сумму",
          "30000" in str(отправлено.get("idempotency")),
          str(отправлено.get("idempotency")))

    # ── Ключи банка действительно включают возврат ─────────────────────
    # Признак «платежи настроены» требовал адрес API и client_id — они есть у
    # Halyk и Forte, но не у FreedomPay, где номер магазина и секретное
    # слово, а адрес зашит в клиенте. Отель вписал бы выданные ему значения,
    # и ничего бы не включилось: поставщик не создаётся, причина видна только
    # в коде.
    живой = _S(payment_provider="freedompay", payment_terminal_id="570767",
               payment_client_secret="секрет")
    check("номера магазина и ключа достаточно для FreedomPay",
          живой.payment_configured)
    провайдер = _get_provider(живой)
    check("поставщик создаётся", getattr(провайдер, "name", "") == "freedompay")
    check("он умеет искать платёж", hasattr(провайдер, "find_payment"))
    check("он умеет возвращать", hasattr(провайдер, "refund"))

    check("без секретного ключа не считается настроенным",
          not _S(payment_provider="freedompay", payment_terminal_id="570767",
                 payment_client_secret="").payment_configured)
    check("без номера магазина не считается настроенным",
          not _S(payment_provider="freedompay", payment_terminal_id="",
                 payment_client_secret="секрет").payment_configured)
    # Старые банки проверяются по-прежнему: правка не должна их сломать.
    check("Halyk по-прежнему проверяется по адресу и client_id",
          _S(payment_provider="epay_halyk", payment_base_url="https://x",
             payment_client_id="id").payment_configured)
    # `_S()` без аргументов читает backend/.env, где теперь лежат боевые
    # ключи, — значит «пустые настройки» надо задавать явно. Ровно на этом
    # проверка и упала, когда ключи появились: она проверяла не то, что
    # написано в её названии.
    check("пустые настройки — платежи не настроены",
          not _S(payment_provider="", payment_terminal_id="",
                 payment_client_secret="", payment_base_url="",
                 payment_client_id="").payment_configured)

    # ── Что видит отель ────────────────────────────────────────────────
    текст = "\n".join(describe(готовый, False, "автоматический возврат выключен"))
    for нужно in ("QA-BRON-NE-SUSHESTVUET", "50000", "QA0000000000"):
        check(f"в сообщении есть «{нужно}»", нужно in текст)
    check("сказано, что делать руками", "кабинете FreedomPay" in текст)

    сделан = "\n".join(describe(готовый, True, "принят банком"))
    check("выполненный возврат назван выполненным", "Возврат отправлен" in сделан)
    check("гостю обещан честный срок", "1–7 рабочих дней" in сделан)

    пусто = "\n".join(describe(полностью, False, полностью.problem))
    check("когда возвращать нечего, заголовок не обещает возврат",
          "не требуется" in пусто, пусто[:60])

    # Проверено на боевом магазине 2026-09-01: выборки транзакций у
    # FreedomPay нет — get_transactions_list.php и соседние отвечают 403 с
    # HTML-страницей. Платёж по номеру брони автоматически не найти, и это
    # штатный исход, а не сбой.
    #
    # Сказать в таком случае «возвращать нечего» — прямо противоположно
    # правде: деньги гостю причитаются. Отель закроет сообщение и не вернёт.
    без_платежа = plan_refund(бронь(), {})
    текст = "\n".join(describe(без_платежа, False, без_платежа.problem))
    check("сумма к возврату названа, хотя платёж не найден",
          "50000" in текст, текст[:80])
    check("не сказано «возвращать нечего», когда деньги причитаются",
          "Возвращать нечего" not in текст, текст[-90:])
    check("сказано, где искать платёж", "my.freedompay.kz" in текст)
    check("сказано, по чему искать", без_платежа.booking in текст)


async def qa_payment_callback() -> None:
    """Приём уведомлений о платежах и поиск платежа по своим записям.

    Это единственный работающий способ связать бронь с платежом. Поддержка
    FreedomPay ответила прямо: искать платежи по описанию через API нельзя,
    «такого API нет». Зато «по каждому платежу мы отправляем коллбэки», и в
    них приходит описание, куда Exely пишет номер брони.

    Адрес приёмника по требованию банка открыт интернету и не требует
    авторизации. Единственная защита — подпись, поэтому её проверка тут
    важнее всего остального: без неё любой желающий объявит платёж
    существующим, а потом по нему уйдут деньги.
    """
    head("Уведомления о платежах")

    import hashlib as _hashlib  # noqa: PLC0415
    import os as _os  # noqa: PLC0415
    import time  # noqa: PLC0415
    import secrets as _sec  # noqa: PLC0415

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from sqlalchemy import delete as _delete  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415

    from app.config import Settings as _S  # noqa: PLC0415
    from app.db import SeenPayment  # noqa: PLC0415
    from app.refunds import _payment_from_own_records  # noqa: PLC0415

    БРОНЬ = f"QA-CB-{int(time.time())}"
    КЛЮЧ = "qa-secret-for-callback"

    настройки = _S(payment_provider="freedompay", payment_terminal_id="570767",
                   payment_client_secret=КЛЮЧ)

    def подписать(поля: dict) -> dict:
        """Подпись уведомления: имя скрипта — последняя часть нашего адреса."""
        script = настройки.payment_result_url.rstrip("/").rsplit("/", 1)[-1]
        parts = [script] + [str(поля[k]) for k in sorted(поля) if k != "pg_sig"]
        parts += [КЛЮЧ]
        поля = dict(поля)
        поля["pg_sig"] = _hashlib.md5(";".join(parts).encode("utf-8")).hexdigest()
        return поля

    def уведомление(**замены) -> dict:
        поля = {
            "pg_payment_id": "1841799001",
            "pg_order_id": "PG1801",
            "pg_description": f"Airis Residence Hotel. {БРОНЬ}. Пётр Петров.",
            "pg_amount": "59634",
            "pg_currency": "KZT",
            "pg_result": "1",
            "pg_card_pan": "4400-43XX-XXXX-9121",
            "pg_salt": _sec.token_hex(8),
        }
        поля.update(замены)
        return подписать(поля)

    async def wipe() -> None:
        async with SessionLocal() as ses:
            await ses.execute(
                _delete(SeenPayment).where(SeenPayment.description.contains(БРОНЬ)))
            await ses.commit()

    await wipe()
    was = _os.environ.get("PAYMENT_CLIENT_SECRET")
    was_provider = _os.environ.get("PAYMENT_PROVIDER")
    was_terminal = _os.environ.get("PAYMENT_TERMINAL_ID")
    _os.environ["PAYMENT_PROVIDER"] = "freedompay"
    _os.environ["PAYMENT_TERMINAL_ID"] = "570767"
    _os.environ["PAYMENT_CLIENT_SECRET"] = КЛЮЧ
    _gs.cache_clear()
    try:
        import app.main as _main  # noqa: PLC0415

        client = TestClient(_main.app)

        # ── Подпись решает всё ─────────────────────────────────────────
        подделка = уведомление()
        подделка["pg_sig"] = "0" * 32
        ответ = client.post("/api/payments/result", data=подделка)
        check("неподписанное уведомление отброшено",
              "bad signature" in ответ.text, ответ.text[:90])
        check("но банку отвечаем 200, а не ошибкой", ответ.status_code == 200)
        async with SessionLocal() as ses:
            from sqlalchemy import select as _select  # noqa: PLC0415
            есть = (await ses.execute(
                _select(SeenPayment).where(
                    SeenPayment.description.contains(БРОНЬ)))).scalars().first()
        check("подделка не попала в базу", есть is None)

        # ── Настоящее уведомление ──────────────────────────────────────
        ответ = client.post("/api/payments/result", data=уведомление())
        check("подписанное уведомление принято", ответ.status_code == 200)
        # Банк ждёт именно XML с подписью, а не слово «ok».
        check("ответ банку — XML", ответ.text.strip().startswith("<?xml"),
              ответ.text[:60])
        for тег in ("pg_status", "pg_description", "pg_salt", "pg_sig"):
            check(f"в ответе есть {тег}", f"<{тег}>" in ответ.text)
        check("ответ говорит об успехе", "<pg_status>ok</pg_status>" in ответ.text)

        # ── Ради чего всё: платёж находится по номеру брони ─────────────
        найден = await _payment_from_own_records(БРОНЬ)
        check("платёж находится по номеру брони из описания",
              найден.get("pg_payment_id") == "1841799001", str(найден)[:90])
        check("сумма сохранена", найден.get("pg_amount") == "59634")
        check("карта сохранена", "9121" in str(найден.get("pg_card_pan")))

        # Повтор того же уведомления — обычное дело, дубля быть не должно.
        client.post("/api/payments/result", data=уведомление())
        async with SessionLocal() as ses:
            from sqlalchemy import func as _func, select as _select  # noqa: PLC0415
            сколько = (await ses.execute(
                _select(_func.count(SeenPayment.payment_id)).where(
                    SeenPayment.description.contains(БРОНЬ)))).scalar()
        check("повтор уведомления не заводит второй платёж", сколько == 1, str(сколько))

        # Неудачный платёж запоминаем, но возвращать по нему нечего.
        client.post("/api/payments/result",
                    data=уведомление(pg_payment_id="1841799002", pg_result="0"))
        найден = await _payment_from_own_records(БРОНЬ)
        check("для возврата берётся оплаченный, а не отказной",
              найден.get("pg_payment_id") == "1841799001",
              str(найден.get("pg_payment_id")))

        # Чужая бронь не должна находиться по нашему номеру.
        check("по неизвестной броне платёж не находится",
              not await _payment_from_own_records("QA-CB-НЕТ-ТАКОЙ"))
    finally:
        await wipe()
        for имя, значение in (("PAYMENT_CLIENT_SECRET", was),
                              ("PAYMENT_PROVIDER", was_provider),
                              ("PAYMENT_TERMINAL_ID", was_terminal)):
            if значение is None:
                _os.environ.pop(имя, None)
            else:
                _os.environ[имя] = значение
        _gs.cache_clear()


async def qa_unpaid() -> None:
    """Брони без предоплаты: сводка отелю через сутки после бронирования.

    Ценность такой сводки держится ровно до первого лишнего пункта. Стоит
    ей набрать чужих броней — её перестанут читать, и вместе с ними
    перестанут замечать настоящие. Поэтому проверяется прежде всего то,
    что в неё НЕ должно попадать.

    Сеть не задействована: разбор ответа Exely вынесен отдельно от запроса
    именно ради этого.
    """
    head("Брони без предоплаты")

    from app.unpaid import Unpaid, describe  # noqa: PLC0415

    # ── Что должно попадать в сводку ───────────────────────────────────
    сводка = "\n".join(describe([
        Unpaid(number="20260901-509506-1262682909", guest="Айтжанов Нурлыбек",
               dates="2026-09-01 → 2026-09-02", room="Standart", amount=34200),
    ]))
    for нужно in ("20260901-509506-1262682909", "Айтжанов Нурлыбек",
                  "2026-09-01", "Standart", "34200"):
        check(f"в сводке есть «{нужно}»", нужно in сводка)
    check("сказано, что делать", "позвонить" in сводка.lower())
    # Гостю мы написать не можем: Exely отдаёт только имя и фамилию, ни
    # телефона, ни почты. Отель должен знать, где искать контакты, иначе
    # первым делом спросит об этом нас.
    check("сказано, где брать контакты гостя", "кабинете Exely" in сводка)
    check("сказано, почему не сами", "в API их нет" in сводка)
    check("в заголовке видно, что речь про сайт", "с сайта" in сводка)

    # ── Разбор ответа Exely ────────────────────────────────────────────
    # Проверяем ту самую развилку, из-за которой сводка едва не наполнилась
    # чужими бронями: 14 из 15 первых проверенных оказались с площадок.
    import app.unpaid as _unpaid  # noqa: PLC0415

    class SETTINGS_STUB:  # noqa: N801 — заглушка, а не класс предметной области
        exely_client_id = exely_client_secret = exely_property_id = "x"
        exely_auth_url = exely_api_base = "https://example.invalid"


    def ответ(**поля):
        основа = {
            "number": "QA-1",
            "status": "Active",
            "source": {"type": "BookingEngine", "code": "PropertySite"},
            "guaranteeInfo": {"totalPrepaid": 0.0},
            "total": {"priceAfterTax": 50000.0},
            "customer": {"lastName": "Петров", "firstName": "Пётр"},
            "roomStays": [{"stayDates": {"arrivalDateTime": "2026-09-10T14:00:00",
                                         "departureDateTime": "2026-09-12T12:00:00"},
                           "roomType": {"name": "Comfort"}}],
        }
        основа.update(поля)
        return {"booking": основа}

    async def разобрать(данные):
        """Прогнать _look с подставным ответом Exely."""
        class _Api:
            def __init__(self, *a, **k) -> None:  # noqa: D107
                pass

            async def _get(self, path):  # noqa: ANN001
                if данные is None:
                    raise RuntimeError("Exely недоступен")
                return данные

        import app.booking_system.exely_api as _ex  # noqa: PLC0415
        было = _ex.ExelyApi
        _ex.ExelyApi = _Api
        try:
            return await _unpaid._look(SETTINGS_STUB, "QA-1")
        finally:
            _ex.ExelyApi = было

    вердикт, item = await разобрать(ответ())
    check("неоплаченная бронь с сайта попадает в сводку", вердикт == "unpaid", вердикт)
    check("имя гостя разобрано", item is not None and item.guest == "Петров Пётр")
    check("даты разобраны", item is not None and item.dates.startswith("2026-09-10"))
    check("категория разобрана", item is not None and item.room == "Comfort")

    # Брони с площадок — не наше дело. Там расчёт по правилам площадки, часто
    # при заезде, и «нет предоплаты» ничего плохого не означает.
    вердикт, _ = await разобрать(ответ(source={"type": "Channel", "code": "BGC"}))
    check("бронь с площадки в сводку не идёт", вердикт == "elsewhere", вердикт)

    вердикт, _ = await разобрать(ответ(guaranteeInfo={"totalPrepaid": 50000.0}))
    check("оплаченная бронь в сводку не идёт", вердикт == "paid", вердикт)

    вердикт, _ = await разобрать(ответ(status="Cancelled"))
    check("отменённая бронь в сводку не идёт", вердикт == "gone", вердикт)

    # Сбой чтения — не то же самое, что «разобрались». Пометив такую бронь
    # проверенной, мы никогда бы к ней не вернулись, и неоплаченная бронь
    # тихо дожила бы до дня заезда.
    вердикт, _ = await разобрать(None)
    check("сбой чтения отделён от разобранного", вердикт == "unreadable", вердикт)

    import inspect  # noqa: PLC0415

    check("непрочитанная бронь не помечается проверенной",
          'verdict == "unreadable"' in inspect.getsource(_unpaid.run))

    # ── Мостик между чатом и бронью ────────────────────────────────────
    # Спросить гостя напрямую можно только так: он называет имя в переписке,
    # то же имя стоит в броне. Exely не отдаёт ни телефона, ни почты, а
    # список броней бесполезен — там тысяча самых старых, новее декабря 2025
    # ничего нет, и никакие фильтры этого не меняют (проверено 2026-09-01 на
    # шести вариантах параметров).
    import time  # noqa: PLC0415

    from sqlalchemy import delete as _del  # noqa: PLC0415

    from app.config import Settings as _S  # noqa: PLC0415
    from app.db import GuestName as _GN  # noqa: PLC0415

    ЧАТ = f"qa-unpaid-{int(time.time())}@c.us"
    ИМЯ = f"тестов тест{int(time.time())}"

    ушло: list = []

    class _Стенд:
        def __init__(self, *a, **k) -> None:  # noqa: D107
            pass

        async def send(self, chat_id: str, text: str) -> str:
            ушло.append((chat_id, text))
            return "stub"

    import app.channels.whatsapp as _wa  # noqa: PLC0415

    настоящий_канал = _wa.WhatsAppChannel
    _wa.WhatsAppChannel = _Стенд
    try:
        бронь = Unpaid(number="QA-U-1", guest=ИМЯ.title(),
                       dates="2026-09-10 → 2026-09-12", room="Comfort", amount=50000)
        # Имени ещё не знаем — гостю не пишем.
        check("без известного имени гостю не пишем",
              not await _unpaid._ask_guest(_S(), бронь))

        async with SessionLocal() as ses:
            ses.add(_GN(channel="whatsapp", chat_id=ЧАТ, name=ИМЯ))
            await ses.commit()
        check("по известному имени гостю пишем",
              await _unpaid._ask_guest(_S(), бронь))
        текст = ушло[-1][1] if ушло else ""
        check("в напоминании названы даты", "2026-09-10" in текст, текст[:70])
        check("напоминание спрашивает, в силе ли планы",
              "планы в силе" in текст, текст[:70])
        # Перенос строки должен быть переносом, а не двумя буквами.
        check("в напоминании нет буквальных переносов",
              chr(92) + "n" not in текст, текст[:70])

        # Однофамильцы: два чата с одним именем — писать нельзя никому.
        # Напомнить чужому человеку о чужой броне значит выдать чужие данные.
        async with SessionLocal() as ses:
            ses.add(_GN(channel="whatsapp", chat_id=ЧАТ + "x", name=ИМЯ))
            await ses.commit()
        ушло.clear()
        check("при двух одинаковых именах не пишем никому",
              not await _unpaid._ask_guest(_S(), бронь))
        check("и ничего не отправлено", not ушло)

        check("без имени в броне гостю не пишем",
              not await _unpaid._ask_guest(_S(), Unpaid(number="QA-U-2", guest="")))
    finally:
        _wa.WhatsAppChannel = настоящий_канал
        async with SessionLocal() as ses:
            await ses.execute(_del(_GN).where(_GN.name == ИМЯ))
            await ses.commit()


async def qa_schema() -> None:
    """Догонка схемы: колонки, добавленные после первого запуска.

    Миграций в проекте нет, новые колонки догоняются списком в `db.py`.
    Раздел появился после полного простоя боевого бэкенда: две булевы
    колонки были записаны как `BOOLEAN DEFAULT 0`, Postgres на нуле для
    BOOLEAN падает, ошибка шла из init_db наверх — и 500 отвечали ВСЕ
    запросы, включая вебхук WhatsApp. Гости писали в пустоту из-за колонки
    в корпоративном разделе.

    Проверяется не «добавляется ли колонка», а то, что сбой одной колонки
    не утаскивает за собой ни соседние, ни запуск приложения.
    """
    head("Догонка схемы базы")

    import os as _os3  # noqa: PLC0415
    import tempfile as _tmp  # noqa: PLC0415
    import importlib as _imp  # noqa: PLC0415

    from sqlalchemy import inspect as _insp2  # noqa: PLC0415

    # Ни одна булева колонка не должна получить DEFAULT 0: Postgres такого
    # не принимает, а падение видно только на боевом.
    import app.db as _db_mod  # noqa: PLC0415

    плохие = [
        f"{таблица}.{имя}"
        for таблица, колонки in _db_mod._LATE_COLUMNS.items()
        for имя, ddl in колонки.items()
        if "BOOLEAN" in ddl.upper() and "DEFAULT 0" in ddl.upper()
    ]
    check("булевых колонок с DEFAULT 0 нет", not плохие, str(плохие))

    # Отдельная база: настоящую трогать нельзя, а проверка меняет схему.
    было_url = _os3.environ.get("DATABASE_URL")
    путь = _tmp.mktemp(suffix=".db").replace("\\", "/")
    _os3.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{путь}"
    try:
        db = _imp.reload(_db_mod)

        async with db.engine.begin() as conn:
            await conn.exec_driver_sql(
                "CREATE TABLE companies (id INTEGER PRIMARY KEY, slug VARCHAR(60))")

        было = db._LATE_COLUMNS["companies"]
        db._LATE_COLUMNS["companies"] = {
            "auto_confirm": "BOOLEAN NOT NULL DEFAULT FALSE",
            "bitaya": "ЧЕПУХА DEFAULT ???",
            "breakfast_price": "INTEGER DEFAULT 0",
        }
        try:
            упало = False
            try:
                await db.init_db()
            except Exception:  # noqa: BLE001
                упало = True
            check("кривая колонка не роняет запуск", not упало)

            async with db.engine.begin() as conn:
                есть = await conn.run_sync(
                    lambda c: {к["name"] for к in _insp2(c).get_columns("companies")})
            check("нужная колонка добавлена", "auto_confirm" in есть, str(sorted(есть)))
            check("соседняя добавлена несмотря на сбой предыдущей",
                  "breakfast_price" in есть, str(sorted(есть)))
            check("кривая колонка не создана", "bitaya" not in есть)

            async with db.engine.begin() as conn:
                await conn.exec_driver_sql("INSERT INTO companies (slug) VALUES ('x')")
                значение = (await conn.exec_driver_sql(
                    "SELECT auto_confirm FROM companies")).scalar()
            # Ложь намеренна: выкатка версии не должна включать
            # авто-подтверждение заявок у тех, кто о нём не просил.
            check("по умолчанию авто-подтверждение выключено", not значение,
                  str(значение))
        finally:
            db._LATE_COLUMNS["companies"] = было
    finally:
        if было_url is None:
            _os3.environ.pop("DATABASE_URL", None)
        else:
            _os3.environ["DATABASE_URL"] = было_url
        _imp.reload(_db_mod)


async def qa_corp_pending() -> None:
    """Очередь «занести в Exely»: единственная ручная работа отеля.

    Занесение автоматизировать нельзя — Exely не создаёт брони извне. Раз
    шаг остаётся человеку, он не должен теряться: пока бронь не занесена,
    номер выглядит свободным и его могут продать второй раз.

    Проверяется в основном то, что в очередь НЕ должно попадать: очередь,
    набравшая лишнего, перестаёт читаться, а вместе с лишним перестают
    замечать настоящее.
    """
    head("Очередь занесения в Exely")

    import time  # noqa: PLC0415
    from datetime import timedelta as _td  # noqa: PLC0415

    from app.corp_api import exely_block  # noqa: PLC0415
    from app.corp_pending import describe, pending  # noqa: PLC0415
    from app.db import (  # noqa: PLC0415
        Company as _C,
        CorpBooking as _CB,
        CorpBookingItem as _CBI,
        utcnow as _now,
    )
    from sqlalchemy import delete as _d3  # noqa: PLC0415

    # ── Блок для переноса ──────────────────────────────────────────────
    класс_брони = _CB(
        number="K-0042", check_in=date(2026, 9, 20), check_out=date(2026, 9, 22),
        nights=2, adults=2, children=1, guest_name="Сериков Ерлан",
        guest_phone="+7 701 555 77 99", meal_plan="breakfast", comment="поздний заезд",
    )
    строки = [_CBI(room_name="Standart", rooms_count=2, price_per_night=25000)]
    блок = exely_block(класс_брони, строки, "Компас")
    for нужно in ("20.09.2026", "22.09.2026", "2 ноч.", "Standart × 2",
                  "2 взр., 1 дет.", "Сериков Ерлан", "+7 701 555 77 99",
                  "завтрак", "Компас", "K-0042", "поздний заезд"):
        check(f"в блоке есть «{нужно}»", нужно in блок, блок[:120])
    check("блок многострочный, а не сплошной", блок.count(chr(10)) >= 5)
    check("в блоке нет буквальных переносов", chr(92) + "n" not in блок, блок[:80])

    # ── Что попадает в очередь, а что нет ──────────────────────────────
    МЕТКА = f"QA-PEND-{int(time.time())}"
    async with SessionLocal() as ses:
        компания = _C(slug=МЕТКА.lower(), name="QA Партнёр", is_active=True)
        ses.add(компания)
        await ses.flush()
        cid = компания.id

        давно = _now() - _td(hours=2)
        только_что = _now()

        варианты = [
            ("ждёт два часа", dict(auto_confirmed=True, status="confirmed",
                                   confirmed_at=давно, entered_at=None), True),
            ("подтверждена минуту назад", dict(auto_confirmed=True, status="confirmed",
                                               confirmed_at=только_что,
                                               entered_at=None), False),
            ("уже занесена", dict(auto_confirmed=True, status="confirmed",
                                  confirmed_at=давно, entered_at=давно), False),
            ("подтвердил человек", dict(auto_confirmed=False, status="confirmed",
                                        confirmed_at=давно, entered_at=None), False),
            ("отменена", dict(auto_confirmed=True, status="cancelled",
                              confirmed_at=давно, entered_at=None), False),
            ("оплачена", dict(auto_confirmed=True, status="paid",
                              confirmed_at=давно, entered_at=None), False),
            ("счёт выставлен, но не занесена",
             dict(auto_confirmed=True, status="invoiced",
                  confirmed_at=давно, entered_at=None), True),
        ]
        номера = {}
        for i, (имя, поля, _) in enumerate(варианты):
            b = _CB(number=f"{МЕТКА}-{i}", company_id=cid,
                    check_in=date(2026, 9, 20), check_out=date(2026, 9, 21),
                    nights=1, adults=1, total_amount=25000, **поля)
            ses.add(b)
            номера[имя] = b.number
        await ses.commit()

    try:
        async with SessionLocal() as ses:
            очередь = {b.number for b in await pending(ses)}
        for имя, _, должна in варианты:
            есть = номера[имя] in очередь
            слово = "попадает" if должна else "НЕ попадает"
            check(f"{имя} — {слово} в очередь", есть == должна,
                  f"в очереди: {есть}")

        # Сводка обязана называть, сколько бронь уже ждёт: без этого она
        # читается как список, а не как «это горит».
        async with SessionLocal() as ses:
            брони = [b for b in await pending(ses) if b.number.startswith(МЕТКА)]
            текст = describe([(b, "QA Партнёр", "блок") for b in брони])
        check("в сводке сказано, сколько не занесено", "Не занесено в Exely" in текст)
        check("названа опасность двойной продажи", "второй раз" in текст, текст[:150])
        check("сказано, сколько ждёт", "ждёт" in текст, текст[:200])
        check("сказано, что делать после", "отметьте в админке" in текст.lower(),
              текст[-120:])
    finally:
        async with SessionLocal() as ses:
            await ses.execute(_d3(_CB).where(_CB.company_id == cid))
            await ses.execute(_d3(_C).where(_C.id == cid))
            await ses.commit()


async def qa_memory_week() -> None:
    """Память на неделю и пометка о паузе.

    Отель попросил помнить разговор неделю: «бывают разные случаи». Длинная
    память опасна одним — в истории нет дат. Проверено 2026-09-13: история
    пятидневной давности, и бот 13 сентября называл цену «на 10–11 сентября»
    как действующую в 2 случаях из 3. Поэтому неделя идёт в паре с пометкой,
    и проверяется в первую очередь пометка.
    """
    head("Память на неделю")

    from datetime import timedelta as _td  # noqa: PLC0415
    import json as _json  # noqa: PLC0415
    import time  # noqa: PLC0415

    from sqlalchemy import delete as _del  # noqa: PLC0415

    from app.concierge import _with_note  # noqa: PLC0415
    from app.db import DialogMessage as _DM, utcnow as _now  # noqa: PLC0415
    from app.dialogs import (  # noqa: PLC0415
        CONTINUES_FOR,
        STALE_AFTER,
        last_message_at,
        pause_hours,
    )

    check("разговор помнится неделю", CONTINUES_FOR == _td(days=7), str(CONTINUES_FOR))
    check("устаревшим разговор считается после суток", STALE_AFTER == _td(hours=24))

    # ── Пауза ──────────────────────────────────────────────────────────
    сейчас = _now()
    check("без переписки паузы нет", pause_hours(None) is None)
    check("пауза считается в часах",
          abs(pause_hours(сейчас - _td(hours=5), сейчас) - 5) < 0.01)
    # SQLite отдаёт время без пояса, Postgres — с поясом. Падать на этом
    # нельзя: из-за пометки гость не должен остаться без ответа.
    наивное = (сейчас - _td(days=2)).replace(tzinfo=None)
    check("время без пояса не роняет расчёт",
          abs(pause_hours(наивное, сейчас) - 48) < 0.01, str(pause_hours(наивное, сейчас)))
    check("время из будущего не даёт отрицательной паузы",
          pause_hours(сейчас + _td(hours=1), сейчас) == 0.0)

    # ── Пометка идёт в запрос, но не в историю ─────────────────────────
    исходные = [
        {"role": "user", "content": "есть Comfort на 10 сентября?"},
        {"role": "assistant", "content": "Свободен, 45 000 ₸."},
        {"role": "user", "content": "а сколько будет стоить?"},
    ]
    с_пометкой = _with_note(исходные, 2, "[пометка]")
    check("пометка встаёт перед репликой гостя",
          с_пометкой[2]["content"][0] == {"type": "text", "text": "[пометка]"})
    check("текст гостя сохранён после пометки",
          с_пометкой[2]["content"][1]["text"] == "а сколько будет стоить?")
    # Список с пометкой уходит только в модель. Исходный потом ложится в
    # историю — и пометка там через неделю читалась бы как действующая.
    check("исходная реплика не изменена", исходные[2]["content"] == "а сколько будет стоить?")
    check("без пометки сообщения не трогаются", _with_note(исходные, 2, "") is исходные)

    # ── История пятидневной давности теперь подхватывается ─────────────
    ЧАТ = f"qa-memory-{int(time.time())}@c.us"
    try:
        async with SessionLocal() as ses:
            for дней, текст in ((9, "девять дней назад"), (5, "пять дней назад")):
                ses.add(_DM(channel="whatsapp", chat_id=ЧАТ, role="user",
                            content=_json.dumps(текст, ensure_ascii=False),
                            created_at=сейчас - _td(days=дней)))
            await ses.commit()

        история = await load_history(SessionLocal, "whatsapp", ЧАТ, depth=12)
        тексты = [m["content"] for m in история]
        check("реплика пятидневной давности помнится", "пять дней назад" in тексты, str(тексты))
        check("старше недели — нет", "девять дней назад" not in тексты, str(тексты))

        последняя = await last_message_at(SessionLocal, "whatsapp", ЧАТ)
        пауза = pause_hours(последняя)
        check("пауза после пяти дней больше суток — пометка сработает",
              пауза is not None and пауза >= STALE_AFTER.total_seconds() / 3600,
              str(пауза))
    finally:
        async with SessionLocal() as ses:
            await ses.execute(_del(_DM).where(_DM.chat_id == ЧАТ))
            await ses.commit()


async def qa_reception_notify() -> None:
    """Корпоративные уведомления — ещё и на ресепшен.

    Просьба отеля: «чтобы наши с ресепшена видели и вносили сразу». Бронь
    компании заносит в шахматку ресепшен, и узнавать о ней он должен сам.

    Проверяется в основном то, что туда НЕ должно уходить: заявки с сайта,
    отмены, суммы возвратов. И то, что ресепшен не отнимает уведомлений у
    владельца. Настоящих отправок нет — канал подменён.
    """
    head("Уведомления ресепшену")

    import inspect as _insp  # noqa: PLC0415
    import os as _os  # noqa: PLC0415

    import app.channels.whatsapp as _wa  # noqa: PLC0415
    import app.corp_pending as _cp  # noqa: PLC0415
    import app.notify as _nt  # noqa: PLC0415
    from app.config import Settings as _S, get_settings as _gs  # noqa: PLC0415

    check("по умолчанию ресепшену ничего не уходит",
          _S(corp_notify_phone="").corp_notify_numbers == [])
    check("номер ресепшена разбирается",
          _S(corp_notify_phone="+7 777 531 00 09").corp_notify_numbers == ["77775310009"])
    # У группы есть звук и пуш у каждого участника — у чата с самим собой нет.
    check("группа WhatsApp принимается как есть",
          _S(corp_notify_phone="120363040000000000@g.us").corp_notify_numbers
          == ["120363040000000000@g.us"])
    check("короткая опечатка отбрасывается",
          _S(corp_notify_phone="555").corp_notify_numbers == [])

    ушло: list[str] = []

    class _Стенд:
        def __init__(self, *a, **k) -> None:  # noqa: D107
            pass

        async def send(self, chat: str, text: str) -> str:
            ушло.append(chat)
            return "stub"

    было_канал = _wa.WhatsAppChannel
    было_env = {k: _os.environ.get(k) for k in ("LEAD_NOTIFY_PHONE", "CORP_NOTIFY_PHONE")}
    _wa.WhatsAppChannel = _Стенд
    try:
        async def кому(corporate: bool, lead: str, corp: str) -> list[str]:
            _os.environ["LEAD_NOTIFY_PHONE"] = lead
            _os.environ["CORP_NOTIFY_PHONE"] = corp
            _gs.cache_clear()
            ушло.clear()
            отправка = getattr(_nt, "_tell_hotel_настоящий", _nt._tell_hotel)
            await отправка("проверка", "qa", corporate=corporate)
            return list(ушло)

        ВЛАДЕЛЕЦ, РЕСЕПШЕН = "77010000001", "77775310009"

        r = await кому(True, ВЛАДЕЛЕЦ, "")
        check("без ресепшена корпоративное уходит как раньше",
              r == [f"{ВЛАДЕЛЕЦ}@c.us"], str(r))

        r = await кому(True, ВЛАДЕЛЕЦ, РЕСЕПШЕН)
        check("корпоративное уходит ресепшену", f"{РЕСЕПШЕН}@c.us" in r, str(r))
        check("и владелец его не теряет", f"{ВЛАДЕЛЕЦ}@c.us" in r, str(r))

        r = await кому(False, ВЛАДЕЛЕЦ, РЕСЕПШЕН)
        check("заявки с сайта и отмены ресепшену НЕ уходят",
              f"{РЕСЕПШЕН}@c.us" not in r, str(r))

        r = await кому(True, РЕСЕПШЕН, "+7 (777) 531-00-09")
        check("один номер в двух списках — одно сообщение",
              r.count(f"{РЕСЕПШЕН}@c.us") == 1, str(r))

        r = await кому(True, ВЛАДЕЛЕЦ, "120363040000000000@g.us")
        check("в группу пишется по её id, без @c.us",
              "120363040000000000@g.us" in r, str(r))

        # Метка должна стоять у обеих корпоративных отправок, иначе ресепшен
        # узнает только о половине.
        check("новая заявка компании помечена корпоративной",
              "corporate=True" in _insp.getsource(_nt.notify_corp_booking))
        check("напоминание «не занесено» тоже",
              "corporate=True" in _insp.getsource(_cp.run))
        check("заявка с сайта — нет",
              "corporate=True" not in _insp.getsource(_nt.notify_whatsapp))
    finally:
        _wa.WhatsAppChannel = было_канал
        for k, v in было_env.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v
        _gs.cache_clear()


async def qa_annotations() -> None:
    """Имена в аннотациях должны существовать — как на Python 3.12.

    Раздел появился после суток простоя боевого сайта. В `corp_api.py`
    обработчик объявлял `data: CorpBookingEnteredIn`, а импорта этой схемы
    не было. Локально всё запускалось и 649 проверок проходили; на сервере
    приложение не поднималось вовсе:

        NameError: name 'CorpBookingEnteredIn' is not defined

    Разница в версии Python. Локально стоит 3.14, где аннотации вычисляются
    лениво (PEP 649) — несуществующее имя в аннотации не всплывает никогда.
    Vercel собирает на 3.12, где аннотация вычисляется сразу, при объявлении
    функции. То есть запуск на своей машине этот класс ошибок физически не
    ловит, и никакая внимательность тут не помогает.

    `get_type_hints` вычисляет аннотации принудительно и на 3.14 — это и
    есть поведение 3.12. Проверяются все обработчики маршрутов: именно их
    FastAPI разбирает при старте, и именно там падение убивает весь сервис.
    """
    head("Имена в аннотациях")

    import typing as _t  # noqa: PLC0415

    import app.main as _main  # noqa: PLC0415

    поломки: list[str] = []
    обработчики: list[tuple[str, object]] = []

    def обойти(маршруты) -> None:
        """Вглубь: подключённые роутеры лежат вложенными объектами.

        Сначала здесь был простой перебор `app.routes` — и он проверял 15
        маршрутов из main.py, а весь корпоративный кабинет пропускал. То
        есть ровно то место, где сломалось, проверка и не видела.
        """
        for маршрут in маршруты or []:
            # FastAPI 0.141 хранит подключённый роутер объектом
            # `_IncludedRouter`, и сами маршруты лежат в `original_router`,
            # а не в `routes`. Учитываем оба вида, чтобы проверка не
            # развалилась молча на следующей версии.
            вложенные = getattr(маршрут, "routes", None)
            внутренний = getattr(маршрут, "original_router", None)
            if вложенные is None and внутренний is not None:
                вложенные = getattr(внутренний, "routes", None)
            if вложенные:
                обойти(вложенные)
                continue
            обработчик = getattr(маршрут, "endpoint", None)
            if обработчик is not None:
                обработчики.append((getattr(маршрут, "path", "?"), обработчик))

    обойти(_main.app.routes)
    for путь, обработчик in обработчики:
        try:
            _t.get_type_hints(обработчик)
        except Exception as error:  # noqa: BLE001
            поломки.append(f"{путь}: {error}")

    сколько = len(обработчики)
    пути = {путь for путь, _ in обработчики}
    check("обработчиков для проверки хватает", сколько > 40, str(сколько))
    # Именно корпоративный кабинет и уронил боевой: если его тут нет,
    # проверка бесполезна.
    check("корпоративный кабинет попал в проверку",
          any("/corp" in путь for путь in пути), str(сколько))
    check("во всех аннотациях обработчиков имена существуют",
          not поломки, "; ".join(поломки[:3]))

    # Те же грабли ждут в моделях Pydantic: там аннотации разбирает сам
    # pydantic, и несуществующее имя роняет импорт модуля.
    from pydantic import BaseModel as _BM  # noqa: PLC0415

    import app.schemas as _sch  # noqa: PLC0415

    кривые: list[str] = []
    моделей = 0
    for имя in dir(_sch):
        значение = getattr(_sch, имя)
        if isinstance(значение, type) and issubclass(значение, _BM) and значение is not _BM:
            моделей += 1
            try:
                _t.get_type_hints(значение)
            except Exception as error:  # noqa: BLE001
                кривые.append(f"{имя}: {error}")
    check("моделей для проверки хватает", моделей > 10, str(моделей))
    check("во всех схемах имена существуют", not кривые, "; ".join(кривые[:3]))


async def qa_undelivered() -> None:
    """Ответ гостю не ушёл — повторяем и говорим отелю.

    2026-09-28 гость написал дважды. Бот оба раза разобрался и сочинил
    ответ — обе реплики лежат в истории, включая проверку наличия на
    12–13 ноября. Но WhatsApp их не принял, и они пропали молча: одна
    попытка отправки, строчка в журнале, и всё.

    Гость сутки ждал ответа. Отель ничего не заметил. Узнали от заказчика
    по скриншоту — то есть самый дорогой способ узнать.

    Отсюда две вещи, и проверяются обе: сбой отправки почти всегда
    проходящий, поэтому пробуем несколько раз; а если не вышло совсем —
    отель должен узнать сразу и получить готовый текст, чтобы ответить
    руками.
    """
    head("Недоставленный ответ гостю")

    import asyncio as _aio  # noqa: PLC0415
    import inspect as _insp  # noqa: PLC0415

    import app.webhooks_api as _wh  # noqa: PLC0415
    from app.channels import WhatsAppError as _WErr  # noqa: PLC0415

    check("попыток отправки больше одной", _wh.ПОПЫТОК_ОТПРАВКИ >= 3,
          str(_wh.ПОПЫТОК_ОТПРАВКИ))

    # Паузы между попытками в проверке ни к чему: они настоящие, а ждать
    # четыре секунды ради трёх строк — плохая сделка.
    настоящий_сон = _aio.sleep

    async def _без_пауз(_секунд):  # noqa: ANN001
        return None

    class _Канал:
        def __init__(self, падений: int) -> None:
            self.падений = падений
            self.попыток = 0

        async def send(self, chat_id: str, text: str) -> str:
            self.попыток += 1
            if self.попыток <= self.падений:
                raise _WErr("WhatsApp не принял")
            return "ok"

    _aio.sleep = _без_пауз
    try:
        # Проходящий сбой — со второй попытки ответ уходит, и гость ничего
        # не замечает. Ради этого случая всё и делалось.
        канал = _Канал(падений=1)
        причина = await _wh._отправить_с_повтором(канал, "77010000000@c.us", "привет")
        check("после первого сбоя ответ всё-таки уходит", причина == "", причина)
        check("и хватило двух попыток", канал.попыток == 2, str(канал.попыток))

        # Сбой не прошёл — сдаёмся, но называем причину.
        канал = _Канал(падений=99)
        причина = await _wh._отправить_с_повтором(канал, "77010000000@c.us", "привет")
        check("при стойком сбое возвращается причина", причина != "")
        check("использованы все попытки",
              канал.попыток == _wh.ПОПЫТОК_ОТПРАВКИ, str(канал.попыток))
    finally:
        _aio.sleep = настоящий_сон

    # ── Что уходит отелю ───────────────────────────────────────────────
    ушло: list[tuple[str, str]] = []

    async def _вместо(text: str, что: str, *, corporate: bool = False) -> int:
        ушло.append((что, text))
        return 1

    import app.notify as _nt  # noqa: PLC0415

    было = _nt._tell_hotel
    _nt._tell_hotel = _вместо
    try:
        await _wh._сказать_отелю_что_ответ_не_ушёл(
            "77019300370", "Есть свободные номера на 12-13 ноября?",
            "На 12–13 ноября свободны Standart и Comfort.", "timeout")
    finally:
        _nt._tell_hotel = было

    check("отелю сообщено", len(ушло) == 1, str(len(ушло)))

    # Проверка бота (proverka_nomera.py) пишет от выдуманного номера, и ответ
    # на него не уходит по определению. Тревога по нему будила бы ресепшн
    # про несуществующего гостя — 2026-10-03 это поймали до первого запуска.
    #
    # Номер берём через тот же разбор, что и у настоящего сообщения, а не
    # пишем руками: первая версия проверки взяла номер без плюса, разбор
    # отдаёт с плюсом — проверка прошла, а тревога на боевом ушла.
    from app.channels.whatsapp import _phone as _номер_из_чата  # noqa: PLC0415

    _nt._tell_hotel = _вместо
    try:
        до = len(ушло)
        await _wh._сказать_отелю_что_ответ_не_ушёл(
            _номер_из_чата(f"{_wh.ПРОВЕРОЧНЫЙ_НОМЕР}@c.us"),
            "во сколько заезд?", "С 14:00.", "invalid chatId")
        check("проверочный номер не поднимает тревогу в отеле", len(ушло) == до,
              f"ушло {len(ушло) - до}")

        # И настоящий гость в том же формате: тревога уходит, номер без «++».
        await _wh._сказать_отелю_что_ответ_не_ушёл(
            _номер_из_чата("77019300370@c.us"), "есть номер?", "Есть.", "timeout")
        текст_гостя = ушло[-1][1] if len(ушло) > до else ""
        check("настоящему гостю тревога уходит", len(ушло) == до + 1, f"ушло {len(ушло) - до}")
        check("номер гостя в тревоге с одним плюсом",
              "Гость: +77019300370" in текст_гостя and "++" not in текст_гостя,
              текст_гостя[:80])
    finally:
        _nt._tell_hotel = было
    # По тексту, а не импортом: скрипт при импорте подменяет вывод в консоль.
    from pathlib import Path as _P  # noqa: PLC0415
    исходник_проверки = (_P(__file__).parent / "proverka_nomera.py").read_text(encoding="utf-8")
    check("скрипт проверки пишет именно с этого номера",
          'TEST_CHAT = f"{ПРОВЕРОЧНЫЙ_НОМЕР}@c.us"' in исходник_проверки)
    текст = ушло[0][1] if ушло else ""
    check("в сообщении виден телефон гостя", "77019300370" in текст, текст[:80])
    check("видно, о чём спрашивал гость", "12-13 ноября" in текст, текст[:120])
    check("приложен готовый ответ для отправки вручную",
          "Standart и Comfort" in текст, текст[-200:])
    check("сказано, что отвечать надо вручную", "вручную" in текст)
    check("названа причина сбоя", "timeout" in текст)

    # Ошибка тарифа приходит JSON-ом, и ресепшн его не прочтёт. 2026-10-04
    # так прошли незамеченными четыре сообщения гостей, один жил в отеле.
    тариф = _wh._понятная_причина(
        'HTTP 466: {"invokeStatus":{"method":"sendmessage","used":21,"total":0,'
        '"status":"QUOTE_ALLOWED","description":"Monthly quota has been exceeded."}}')
    check("кончился тариф Green API — сказано словами", "тариф" in тариф and "{" not in тариф, тариф)
    check("и что делать — оплатить Business", "Business" in тариф)

    # Обработчик вебхука обязан этим пользоваться: без вызова всё
    # вышесказанное — мёртвый код.
    исходник = _insp.getsource(_wh)
    check("вебхук отправляет с повтором", "_отправить_с_повтором(" in исходник)
    check("и зовёт оповещение при сбое",
          "_сказать_отелю_что_ответ_не_ушёл(" in исходник)


async def qa_chat_turn() -> None:
    """Два сообщения одного чата — по очереди, а не параллельно.

    2026-10-05 гость написал «будем к обеду» и через 20 секунд «около 12:00».
    Ответы собирались одновременно, второй не видел первого, и гость дважды
    подряд услышал про ранний заезд и про номер брони.
    """
    head("Очередь ответов в чате")

    import asyncio as _aio  # noqa: PLC0415

    import app.dialogs as _dl  # noqa: PLC0415
    from app.concierge import build_system_prompt  # noqa: PLC0415
    from app.db import SessionLocal  # noqa: PLC0415
    from app.knowledge import render_brief  # noqa: PLC0415

    журнал: list[str] = []
    чат = f"7701{int(_aio.get_event_loop().time() * 1000) % 10_000_000:07d}@c.us"

    async def _ответ(имя: str, пауза: float) -> None:
        async with _dl.chat_turn(SessionLocal, "whatsapp", чат):
            журнал.append(f"начал {имя}")
            await _aio.sleep(пауза)
            журнал.append(f"кончил {имя}")

    было = _dl.TURN_WAIT_SECONDS
    try:
        await _aio.gather(_ответ("первый", 1.0), _ответ("второй", 0.1))
    finally:
        _dl.TURN_WAIT_SECONDS = было
    check("второе сообщение ждёт, пока отвечено первое",
          журнал in (["начал первый", "кончил первый", "начал второй", "кончил второй"],
                     ["начал второй", "кончил второй", "начал первый", "кончил первый"]), str(журнал))

    # Другой чат не ждёт: очередь — внутри одного разговора.
    журнал.clear()
    async def _в_чате(чат_id: str) -> None:
        async with _dl.chat_turn(SessionLocal, "whatsapp", чат_id):
            журнал.append("вошёл")
            await _aio.sleep(0.5)
    t0 = _aio.get_event_loop().time()
    await _aio.gather(_в_чате(чат), _в_чате(чат.replace("7701", "7702")))
    check("разные чаты не ждут друг друга", _aio.get_event_loop().time() - t0 < 0.9)

    import inspect as _insp  # noqa: PLC0415
    import app.webhooks_api as _wh  # noqa: PLC0415
    check("вебхук отвечает по очереди", "chat_turn(" in _insp.getsource(_wh.whatsapp_webhook))

    правила = build_system_prompt("", "2026-10-05", availability="exely")
    check("вопрос в конце — только когда есть следующий шаг",
          "Но вопрос — только когда есть следующий шаг" in правила)
    check("сказанное не повторять", "Не повторяй сказанное в этом разговоре" in правила)
    check("номер брони — только когда без него не обойтись",
          "Номер брони спрашивай, только если" in правила)
    бриф = render_brief({"hotel": {}, "policy": {}})
    check("про хранение багажа — прямая строка, не обещать",
          "Хранение багажа: в справке НЕ указано" in бриф)
    check("подтверждённое хранение багажа попадает в бриф",
          "Хранение багажа: бесплатно" in render_brief({"hotel": {}, "policy": {"luggage": "бесплатно"}}))


async def qa_guest_messages_language() -> None:
    """Сообщения по брони — на языке гостя и с ссылкой на отзыв.

    Отель бронирует Европа, а «спасибо за бронирование», «завтра ждём» и
    просьба об отзыве уходили всем по-русски. А в просьбе об отзыве не было
    ссылки — гость не знал, куда его писать (найдено 2026-10-05).
    """
    head("Сообщения по брони: язык и отзыв")

    import inspect as _insp  # noqa: PLC0415

    import app.lifecycle as _lc  # noqa: PLC0415
    from app.guest_messages import (  # noqa: PLC0415
        AFTER_DEPARTURE, BEFORE_ARRIVAL, BOOKING_CANCELLED, BOOKING_CREATED, for_guest,
        render, review_url,
    )

    check("казахстанскому номеру — по-русски", for_guest(BOOKING_CREATED, "+77019300370") == BOOKING_CREATED)
    check("российскому — тоже", for_guest(BEFORE_ARRIVAL, "79161234567") == BEFORE_ARRIVAL)
    for имя, шаблон in (("подтверждение", BOOKING_CREATED), ("накануне", BEFORE_ARRIVAL),
                        ("после выезда", AFTER_DEPARTURE), ("отмена", BOOKING_CANCELLED)):
        англ = for_guest(шаблон, "+8615712455710")
        check(f"иностранцу «{имя}» — по-английски",
              англ != шаблон and not any("а" <= ch <= "я" for ch in англ.lower()), англ[:60])

    check("отзыв: Казахстан → 2ГИС", "2gis.kz" in review_url("+77019300370"))
    check("отзыв: Россия → Яндекс", "yandex" in review_url("+79161234567"))
    check("отзыв: иностранец → TripAdvisor", "tripadvisor" in review_url("+447700900123"))
    после = render(AFTER_DEPARTURE, name="Анна", review_url=review_url("+77019300370"))
    check("в просьбе об отзыве есть ссылка", "https://2gis.kz/" in после, после[-140:])

    исходник = _insp.getsource(_lc)
    check("рассылка выбирает язык по номеру", исходник.count("for_guest(") >= 3)
    check("и подставляет ссылку на отзыв", "review_url(" in исходник)


async def qa_followup_own() -> None:
    """Дожим не пишет на свои номера — ресепшну, Айнур, разработчику."""
    head("Дожим и свои номера")

    import app.followup as _fu  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415

    settings = _gs()
    было = (_fu._stale_chats, _fu._step_for, _fu._history, _fu._decide, _fu.load_facts,
            _fu._staff_spoke,
            settings.followup_since, settings.lead_notify_phone, settings.dev_alert_phone)

    async def _без_сотрудника(_session, _chat, hours: int = 48):  # noqa: ANN001
        return False

    async def _залежались(_session, *, stale_hours, since):  # noqa: ANN001
        return [("77775310009@c.us", 3), ("77087241460@c.us", 3), ("77010000001@c.us", 3)]

    async def _шаг(_session, _chat, **_kw):  # noqa: ANN001
        return 1

    async def _история(_session, _chat):  # noqa: ANN001
        return [{"role": "user", "text": "Уважаемый гость, ждём вас"}]

    async def _решение(*_a, **_kw):  # noqa: ANN001
        return True, "пропал после цены", "Мы смотрели для вас Comfort…"

    async def _факты(_settings, force: bool = False):  # noqa: ANN001
        return {"hotel": {}, "policy": {}, "rooms": []}

    _fu._stale_chats, _fu._step_for, _fu._history, _fu._decide, _fu.load_facts = (
        _залежались, _шаг, _история, _решение, _факты)
    _fu._staff_spoke = _без_сотрудника
    settings.followup_since = "2026-10-05T12:00"
    settings.lead_notify_phone = "+7 777 531 00 09"
    settings.dev_alert_phone = "+77087241460"
    try:
        nudges = await _fu.plan(None, settings)
        кому = {n.chat_id for n in nudges}
        check("ресепшну дожим не пишет", "77775310009@c.us" not in кому)
        check("разработчику — тоже", "77087241460@c.us" not in кому)
        check("а гостю пишет", "77010000001@c.us" in кому, str(кому))
    finally:
        (_fu._stale_chats, _fu._step_for, _fu._history, _fu._decide, _fu.load_facts,
         _fu._staff_spoke,
         settings.followup_since, settings.lead_notify_phone, settings.dev_alert_phone) = было


async def qa_booking_sync() -> None:
    """Перенос броней из Exely читает все страницы, ближайшие заезды — первыми.

    2026-10-05 гость с бронью на сегодня (через Booking.com) по фамилии не
    нашёлся: перенос читал одну страницу списка из семи, и свежих броней в
    своей копии не было три дня. Номер Booking.com бот отправил в Exely,
    получил 400 и сказал гостю, что «система не ответила».
    """
    head("Перенос броней из Exely и поиск по фамилии")

    from datetime import date as _d

    from sqlalchemy import delete as _del

    import app.booking_sync as _bs
    import app.booking_system.exely_api as _ea
    from app.booking_system.base import BookingSystemUnavailable as _Unavail
    from app.concierge import _tool_find
    from app.db import ExelyBooking as _EB, SessionLocal as _S, init_db as _init

    await _init()
    QA = "-999999-"
    сегодня = _d(2026, 10, 5)

    def _сводка(номер: str, статус: str = "Active", правка: str = "2026-10-05T07:00:00Z",
                создана: str = "2026-10-04T11:00:00Z") -> dict:
        return {"number": номер, "status": статус, "modifiedDateTime": правка,
                "createdDateTime": создана, "propertyId": "999999"}

    def _деталь(сводка: dict, фамилия: str, заезд: str, выезд: str) -> dict:
        return {"number": сводка["number"], "status": сводка["status"],
                "customer": {"lastName": фамилия, "firstName": "James"},
                "roomStays": [{"stayDates": {"arrivalDateTime": f"{заезд}T14:00",
                                             "departureDateTime": f"{выезд}T12:00"},
                               "roomType": {"name": "Comfort +"}}],
                "total": {"priceAfterTax": 45000.0},
                # Exely округляет время в детали иначе, чем в сводке: на
                # живых бронях разница в секунду.
                "modifiedDateTime": сводка["modifiedDateTime"].replace(":00Z", ":59Z")}

    старая = _сводка(f"20250110{QA}0000000001", правка="2025-01-01T00:00:00Z",
                     создана="2024-12-01T00:00:00Z")
    через_месяц = _сводка(f"20261105{QA}0000000002", создана="2026-10-01T00:00:00Z")
    сегодняшняя = _сводка(f"20261005{QA}0000000003")
    отменённая = _сводка(f"20261010{QA}0000000004", статус="Cancelled",
                         правка="2026-10-05T08:00:00Z")
    страницы = {
        "": {"bookingSummaries": [старая, через_месяц], "hasMoreData": True, "continueToken": "t1"},
        "t1": {"bookingSummaries": [отменённая], "hasMoreData": True, "continueToken": "t2"},
        "t2": {"bookingSummaries": [сегодняшняя], "hasMoreData": False, "continueToken": "t3"},
    }
    детали = {
        старая["number"]: _деталь(старая, "Old", "2025-01-10", "2025-01-11"),
        через_месяц["number"]: _деталь(через_месяц, "Later", "2026-11-05", "2026-11-07"),
        сегодняшняя["number"]: _деталь(сегодняшняя, "Qagibson", "2026-10-05", "2026-10-06"),
        отменённая["number"]: _деталь(отменённая, "Cancelson", "2026-10-10", "2026-10-12"),
    }

    class _Api:
        _rows = staticmethod(_ea.ExelyApi._rows)

        def __init__(self) -> None:
            self.токены: list[str] = []
            self.детали: list[str] = []

        async def _get(self, path: str, params=None, **_kw):  # noqa: ANN001
            if path.endswith("/bookings"):
                token = (params or {}).get("continueToken", "")
                self.токены.append(token)
                return страницы[token]
            number = path.rsplit("/", 1)[-1]
            self.детали.append(number)
            return {"booking": детали[number]}

    async with _S() as sess:
        await sess.execute(_del(_EB).where(_EB.number.like(f"%{QA}%")))
        # Отменённая уже лежит у нас «живой» — так было с бронями, отменёнными
        # после переноса: статус не обновлялся до перечитывания.
        sess.add(_EB(number=отменённая["number"], status="Active", guest_name="Cancelson James",
                     guest_search="cancelson james", check_in=_d(2026, 10, 10),
                     check_out=_d(2026, 10, 12), modified_at="2026-09-28T00:00:00Z"))
        await sess.commit()

    api = _Api()
    async with _S() as sess:
        r = await _bs.sync(sess, api, "999999", today=сегодня, budget=0)
    check("читаются все страницы списка по continueToken", api.токены == ["", "t1", "t2"],
          str(api.токены))
    check("без времени на детали — ни одной детали", r["перенесено"] == 0 and not api.детали,
          str(r))
    check("отмена видна по сводке, без детального запроса", r["статус обновлён"] >= 1, str(r))
    async with _S() as sess:
        check("отменённая бронь у нас больше не «Active»",
              (await sess.get(_EB, отменённая["number"])).status == "Cancelled")
    check("старая история в очередь не попадает", r["осталось в очереди"] == 3, str(r))

    api = _Api()
    async with _S() as sess:
        r = await _bs.sync(sess, api, "999999", limit=1, today=сегодня)
    check("первой переносится бронь с заездом сегодня", api.детали == [сегодняшняя["number"]],
          str(api.детали))

    api = _Api()
    async with _S() as sess:
        r = await _bs.sync(sess, api, "999999", today=сегодня)
    check("остальные нужные переносятся следующим запуском",
          sorted(api.детали) == sorted([через_месяц["number"], отменённая["number"]]),
          str(api.детали))
    check("прошлогодняя бронь не запрашивается вовсе", старая["number"] not in api.детали)

    api = _Api()
    async with _S() as sess:
        r = await _bs.sync(sess, api, "999999", today=сегодня)
    check("повторный запуск ничего не перечитывает, хотя время в детали другое",
          r["перенесено"] == 0 and not api.детали, str(r))

    async with _S() as sess:
        # Фамилия выдуманная: в локальной базе могут лежать настоящие брони.
        найдено = await _bs.find_by_name(sess, "James Qagibson", arrival=сегодня)
        check("«James Qagibson» находит «Qagibson James» с заездом сегодня",
              [b.number for b in найдено] == [сегодняшняя["number"]], str([b.number for b in найдено]))
        check("короткое «Mr» не мешает поиску",
              len(await _bs.find_by_name(sess, "Mr Qagibson", arrival=сегодня)) == 1)
        check("с другой датой заезда не выдаётся",
              not await _bs.find_by_name(sess, "Qagibson", arrival=_d(2026, 10, 6)))
    check("номер брони даёт дату заезда", _bs.arrival_of("20261005-509506-1265394803") == сегодня)
    check("номер Booking.com датой не считается", _bs.arrival_of("6359909102") is None)

    class _ExelyLike:
        finds_by_phone = False

        def __init__(self) -> None:
            self.спрошено: list[str] = []

        async def find_bookings(self, *, phone: str = "", name: str = ""):
            return []

        async def get_booking(self, ref: str):
            self.спрошено.append(ref)
            return None

    гость = {"phone": "+447542253459"}
    система = _ExelyLike()
    ответ = await _tool_find(система, {"ref": "6359909102"}, гость)
    check("номер Booking.com в Exely не отправляется", система.спрошено == [], str(система.спрошено))
    check("и бот ищет по фамилии и дате, а не просит номер снова",
          "не номер брони отеля" in ответ and "name и arrival" in ответ, ответ[:120])
    ответ = await _tool_find(система, {"ref": "20261005-509506-1265394803"}, гость)
    check("номер отеля ищется в Exely", система.спрошено == ["20261005-509506-1265394803"])
    ответ = await _tool_find(система, {"name": "James Qagibson", "arrival": "2026-10-05"}, гость)
    check("по фамилии и дате заезда бронь находится", сегодняшняя["number"] in ответ, ответ[:120])

    # Exely на чужой номер отвечает 400 — это «брони нет», а не сбой.
    настоящий = _ea.httpx.AsyncClient
    api400 = _ea.ExelyApi("id", "secret", "999999", auth_url="https://a/token",
                          api_base="https://b")

    async def _токен() -> str:
        return "t"

    api400.token = _токен
    _ea.httpx.AsyncClient = lambda **kw: настоящий(
        transport=httpx.MockTransport(lambda request: httpx.Response(400, text="bad number")),
        **{k: v for k, v in kw.items() if k != "transport"})
    try:
        check("400 на номер брони — «такой брони нет»", await api400.get_booking("6359909102") is None)
        try:
            await api400._get("/v1/properties/999999/bookings")
            маскировано = True
        except _Unavail:
            маскировано = False
        check("400 на список по-прежнему ошибка, а не пустой отель", not маскировано)
    finally:
        _ea.httpx.AsyncClient = настоящий

    async with _S() as sess:
        await sess.execute(_del(_EB).where(_EB.number.like(f"%{QA}%")))
        await sess.commit()

    правила = build_system_prompt("", "2026-10-05", availability="exely")
    check("названия номеров с Booking.com гостю не поправляют",
          "Не говори, что такого номера нет" in правила)


async def qa_daily_check() -> None:
    """Ежедневная проверка бота находит то, что ломалось молча.

    4 октября 2026 бот сутки не отвечал гостям — кончился тариф Green API, —
    и узнали по жалобе. Проверка должна поймать это сама.
    """
    head("Ежедневная проверка бота")

    import time as _t  # noqa: PLC0415

    import app.daily_check as _dc  # noqa: PLC0415
    import app.knowledge as _kn  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415
    from app.booking_system.base import Availability as _Av, RoomOffer as _Ro  # noqa: PLC0415

    сейчас = int(_t.time())

    баланс = {"пуст": False, "запросов": 0}
    НЕТ_БАЛАНСА = httpx.Response(400, json={"type": "error", "error": {
        "type": "invalid_request_error",
        "message": "Your credit balance is too low to access the Anthropic API."}})

    def _зелёный(исходящие: list[dict]) -> httpx.MockTransport:
        def _ответ(request: httpx.Request) -> httpx.Response:
            путь = request.url.path
            if путь.endswith("/v1/messages"):
                баланс["запросов"] += 1
                if баланс["пуст"]:
                    return НЕТ_БАЛАНСА
                return httpx.Response(200, json={"content": [{"type": "text", "text": "o"}]})
            if "getStateInstance" in путь:
                return httpx.Response(200, json={"stateInstance": "authorized"})
            if "getSettings" in путь:
                return httpx.Response(200, json={
                    "wid": "77003002526@c.us", "incomingWebhook": "yes", "incomingCallWebhook": "yes",
                    "outgoingMessageWebhook": "yes",
                    "webhookUrl": "https://airisresidence.kz/api/backend/api/webhooks/whatsapp?key=x"})
            if "lastOutgoingMessages" in путь:
                return httpx.Response(200, json=исходящие)
            if "count_tokens" in путь:
                return httpx.Response(200, json={"input_tokens": 9})
            if путь.endswith("/models"):
                return httpx.Response(200, json={"data": []})
            return httpx.Response(404)
        return httpx.MockTransport(_ответ)

    class _Exely:
        async def availability(self, check_in, check_out, *, guests=2):  # noqa: ANN001
            return _Av(check_in, check_out, 1, [_Ro(room_slug="comfort", room_name="Comfort",
                                                    rooms_left=3, price_per_night=45000,
                                                    source="exely")], "exely")

    async def _факты(_settings, force: bool = False):  # noqa: ANN001
        return {"rooms": [{"slug": "comfort"}]}

    import app.db as _db  # noqa: PLC0415
    from datetime import datetime as _dt, timezone as _tz  # noqa: PLC0415

    свежесть = {"последняя": _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    class _Итог:
        def scalar(self):  # noqa: ANN201
            return свежесть["последняя"]

    class _Сессия:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *_a) -> bool:
            return False

        async def execute(self, *_a, **_k) -> _Итог:
            return _Итог()

    было_сессии = _db.SessionLocal
    _db.SessionLocal = lambda: _Сессия()
    настоящий_клиент = _dc.httpx.AsyncClient
    было_факты = _kn.load_facts
    settings = _gs()
    было_настройки = (settings.green_api_id, settings.green_api_token, settings.lead_notify_phone,
                      settings.anthropic_api_key, settings.speech_api_key)
    settings.green_api_id, settings.green_api_token = "1", "t"
    settings.lead_notify_phone, settings.anthropic_api_key = "77775310009", "k"
    settings.speech_api_key = "s"
    _kn.load_facts = _факты
    try:
        def _клиент(исходящие):
            транспорт = _зелёный(исходящие)
            return lambda **kw: настоящий_клиент(transport=транспорт, **{k: v for k, v in kw.items() if k != "transport"})

        _dc.httpx.AsyncClient = _клиент([])
        r = await _dc.run(settings, booking=_Exely())
        check("здоровый бот — без замечаний", r["ok"] and not r["problems"], str(r["problems"])[:160])
        check("баланс проверяется настоящим запросом на один токен", баланс["запросов"] == 1)

        # 2026-10-05: деньги на ключе кончились — подсчёт токенов мог пройти,
        # а гости весь день получали запасную фразу.
        баланс["пуст"] = True
        r = await _dc.run(settings, booking=_Exely())
        check("пустой баланс Anthropic пойман", any("кончились деньги" in p for p in r["problems"]),
              str(r["problems"])[:160])
        баланс["пуст"] = False

        # 2026-10-05: перенос броней стоял три дня, и гость с бронью на
        # сегодня по фамилии не нашёлся. Проверка это теперь видит.
        свежесть["последняя"] = (_dt.now(_tz.utc) - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = await _dc.run(settings, booking=_Exely())
        check("отставший перенос броней пойман", any("перенос броней" in p for p in r["problems"]),
              str(r["problems"])[:160])
        свежесть["последняя"] = None
        r = await _dc.run(settings, booking=_Exely())
        check("пустая копия броней поймана", any("копия броней пуста" in p for p in r["problems"]),
              str(r["problems"])[:160])
        свежесть["последняя"] = _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Тариф кончился: тревога с 466 и после неё — ни одного сообщения наружу.
        тревога = {"chatId": "77003002526@c.us", "timestamp": сейчас - 600, "statusMessage": "sent",
                   "textMessage": "🔴 Гость написал, а ответ НЕ УШЁЛ ... HTTP 466: quota"}
        _dc.httpx.AsyncClient = _клиент([тревога])
        r = await _dc.run(settings, booking=_Exely())
        check("упор в лимит тарифа пойман", any("лимит тарифа" in p for p in r["problems"]),
              str(r["problems"])[:160])

        # После оплаты ответы снова уходят — старые тревоги уже не проблема.
        ответ = {"chatId": "77019300370@c.us", "timestamp": сейчас - 60, "statusMessage": "delivered",
                 "textMessage": "Здравствуйте!"}
        _dc.httpx.AsyncClient = _клиент([тревога, ответ])
        r = await _dc.run(settings, booking=_Exely())
        check("после оплаты лимит не считается проблемой",
              not any("лимит тарифа" in p for p in r["problems"]), str(r["problems"])[:160])

        settings.lead_notify_phone = ""
        _dc.httpx.AsyncClient = _клиент([])
        r = await _dc.run(settings, booking=_Exely())
        check("без получателя уведомлений — замечание",
              any("LEAD_NOTIFY_PHONE" in p for p in r["problems"]))
        текст = _dc.describe(r)
        check("сообщение разработчику перечисляет проблемы",
              "LEAD_NOTIFY_PHONE" in текст and "proverka_nomera.py" in текст)
    finally:
        _db.SessionLocal = было_сессии
        _dc.httpx.AsyncClient = настоящий_клиент
        _kn.load_facts = было_факты
        (settings.green_api_id, settings.green_api_token, settings.lead_notify_phone,
         settings.anthropic_api_key, settings.speech_api_key) = было_настройки

    import inspect as _insp  # noqa: PLC0415

    import app.webhooks_api as _wh  # noqa: PLC0415

    исходник = _insp.getsource(_wh.daily_check)
    check("точка проверки защищена ключом", "_presented(request) != secret" in исходник)
    check("и пишет разработчику при проблемах", "tell_developer(" in исходник)
    check("тревога о неушедшем ответе идёт и разработчику",
          "tell_developer(" in _insp.getsource(_wh._сказать_отелю_что_ответ_не_ушёл))


async def qa_credits_alert() -> None:
    """Кончились деньги на ключе — разработчик узнаёт сразу, но не на каждое сообщение.

    2026-10-05 баланс Anthropic опустел, бот отвечал гостям запасной фразой,
    и узнали об этом не от бота.
    """
    head("Тревога: кончились кредиты Anthropic")

    import app.concierge as _c  # noqa: PLC0415
    import app.notify as _nt  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415

    ушло: list[str] = []

    async def _разработчику(text: str, что: str) -> int:
        ушло.append(text)
        return 1

    def _нет_денег(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"type": "error", "error": {
            "type": "invalid_request_error",
            "message": "Your credit balance is too low to access the Anthropic API."}})

    import app.dialogs as _dl  # noqa: PLC0415

    # Ключ «уже говорили в этот час» — в памяти, чтобы повторный прогон QA
    # не упирался в запись из прошлого прогона.
    виденные: set[str] = set()

    async def _seen(_sessions, channel: str, message_id: str) -> bool:
        ключ = f"{channel}:{message_id}"
        if ключ in виденные:
            return True
        виденные.add(ключ)
        return False

    settings = _gs()
    было = (settings.anthropic_api_key, _nt.tell_developer, _c.httpx.AsyncClient)
    было_seen = _dl.seen_before
    _dl.seen_before = _seen
    настоящий_клиент = _c.httpx.AsyncClient
    settings.anthropic_api_key = "k"
    _nt.tell_developer = _разработчику
    _c.httpx.AsyncClient = lambda **kw: настоящий_клиент(
        transport=httpx.MockTransport(_нет_денег), **{k: v for k, v in kw.items() if k != "transport"})
    try:
        гость = {"name": "QA", "phone": "+77010000000", "chat_id": "77010000000@c.us"}
        первый = await _c.answer(settings, message="Здравствуйте", history=[], today="2026-10-05",
                                 guest=гость)
        await _c.answer(settings, message="Есть номер?", history=[], today="2026-10-05", guest=гость)
    finally:
        settings.anthropic_api_key, _nt.tell_developer, _c.httpx.AsyncClient = было
        _dl.seen_before = было_seen
    check("гость получает запасной ответ", bool(первый.get("text")))
    check("разработчику ушла тревога о кончившихся деньгах",
          any("кончились деньги" in t for t in ушло), str(ушло)[:160])
    check("и только одна за час, а не на каждое сообщение", len(ушло) <= 1, str(len(ушло)))


async def qa_numeric_history() -> None:
    """Реплика из одних цифр не ломает историю разговора.

    2026-10-05 гость прислал номер брони Booking.com «6359909102». В истории
    он лежал строкой, а при чтении json.loads превратил его в число; модель
    на такую историю отвечает 400, и гость до конца разговора получал только
    «позвоните на стойку». Так же сломал бы разговор ответ «2» на вопрос о
    числе гостей.
    """
    head("История: реплики из одних цифр")

    import time as _t  # noqa: PLC0415

    import app.concierge as _c  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415
    from app.dialogs import content_of, load_history, save_turn  # noqa: PLC0415

    чат = f"44{int(_t.time() * 1000) % 10_000_000_000:010d}@c.us"
    await save_turn(SessionLocal, "whatsapp", чат, [
        {"role": "user", "content": "6359909102"},
        {"role": "assistant", "content": "Thank you."},
        {"role": "user", "content": "2"},
        {"role": "assistant", "content": "true"},
        {"role": "user", "content": "null"},
        {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
    ], 0)
    история = await load_history(SessionLocal, "whatsapp", чат)
    типы = [type(m["content"]).__name__ for m in история]
    check("номер брони цифрами читается строкой", история and история[0]["content"] == "6359909102",
          str(история[:1]))
    check("«2», «true», «null» — тоже строками, список блоков — списком",
          типы == ["str", "str", "str", "str", "str", "list"], str(типы))
    check("строка JSON читается как строка", content_of('"привет"') == "привет")

    # И страховка в самом консьерже: что бы ни пришло, в модель уходит строка.
    запросы: list[dict] = []

    async def _модель(payload, headers, **_kw):  # noqa: ANN001
        запросы.append(payload)
        return {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "usage": {}}

    async def _факты(_settings, force: bool = False):  # noqa: ANN001
        return {"hotel": {}, "policy": {}, "rooms": []}

    settings = _gs()
    было = (settings.anthropic_api_key, _c._call_model, _c.load_facts)
    settings.anthropic_api_key, _c._call_model, _c.load_facts = "k", _модель, _факты
    try:
        await _c.answer(settings, message="It’s for today",
                        history=[{"role": "user", "content": 6359909102},
                                 {"role": "assistant", "content": "Thank you."}],
                        today="2026-10-05", guest={"phone": "+447542253459"})
    finally:
        settings.anthropic_api_key, _c._call_model, _c.load_facts = было
    содержимое = [type(m["content"]).__name__ for m in (запросы[-1]["messages"] if запросы else [])]
    check("в модель не уходит число вместо текста",
          bool(содержимое) and all(t in ("str", "list") for t in содержимое), str(содержимое))


async def qa_guest_language_everywhere() -> None:
    """Язык гостя — во всех ответах, и в тех, что уходят без модели.

    2026-10-05 гость из Великобритании писал по-английски, а запасные ответы
    («не могу свериться с ценами») и ответы на его снимки брони («не
    платёжный документ») приходили по-русски — семь раз за двадцать минут.
    Он перешёл на «Spasibo» и казахский, в чат вмешался сотрудник. Тревоги
    при этом не было: она срабатывала только на кончившиеся деньги.
    """
    head("Язык гостя во всех ответах и тревога о запасном ответе")

    import re as _re  # noqa: PLC0415
    import time as _t  # noqa: PLC0415
    from types import SimpleNamespace as _NS  # noqa: PLC0415

    import app.channels.flow as _fl  # noqa: PLC0415
    import app.concierge as _c  # noqa: PLC0415
    import app.dialogs as _dl  # noqa: PLC0415
    import app.followup as _fu  # noqa: PLC0415
    import app.notify as _nt  # noqa: PLC0415
    import app.webhooks_api as _wh  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415
    from app.guest_messages import (  # noqa: PLC0415
        CANT_ANSWER, FILE_RECEIVED, PAYMENT_APPLIED, PAYMENT_DUPLICATE, PAYMENT_NEEDS_CHECK,
        UNREADABLE, VOICE_NOT_SUPPORTED, guest_language, in_language,
    )

    кириллица = _re.compile("[а-яёА-ЯЁәғқңөұүһіӘҒҚҢӨҰҮҺІ]")

    # 1. Как понимается язык.
    check("английская фраза — английский",
          guest_language("We will be there at mid day", "+447542253459") == "en")
    check("русская — русский", guest_language("Будем к обеду", "+77010000000") == "ru")
    check("казахская — казахский",
          guest_language("Сағат 14:00-де кездесеміз", "+77010000000") == "kk")
    check("номер брони цифрами — по прошлым репликам гостя",
          guest_language("6359909102", "+447542253459", ["It’s for today"]) == "en")
    check("цифры без истории, иностранный номер — английский",
          guest_language("6359909102", "+447542253459") == "en")
    check("цифры без истории, номер +7 — русский",
          guest_language("6359909102", "+77010000000") == "ru")
    check("«ok» в русском разговоре — русский",
          guest_language("ok", "+77010000000", ["Есть номер на завтра?"]) == "ru")
    check("«Comfort Plus» в русском разговоре — русский",
          guest_language("Comfort Plus", "+77010000000", ["Какие номера есть?"]) == "ru")
    check("длинная английская фраза меняет язык разговора",
          guest_language("Could you please send me the link to book it",
                         "+77010000000", ["Какие номера есть?"]) == "en")

    # 2. Все тексты без модели — на трёх языках, английский без кириллицы.
    тексты = {"запасной ответ": CANT_ANSWER, "нечитаемое": UNREADABLE, "файл": FILE_RECEIVED,
              "платёж на проверке": PAYMENT_NEEDS_CHECK, "платёж записан": PAYMENT_APPLIED,
              "платёж повтором": PAYMENT_DUPLICATE, "голосовое": VOICE_NOT_SUPPORTED}
    for имя, варианты in тексты.items():
        check(f"«{имя}» — на русском, английском и казахском", set(варианты) >= {"ru", "en", "kk"})
        английский = in_language(варианты, "en", phone="+7 (777) 531-00-09", ref="R-1", amount=1000)
        check(f"«{имя}» по-английски — без единой русской буквы", not кириллица.search(английский),
              английский[:80])
        check(f"«{имя}» — подстановки раскрыты", "{" not in английский)

    # 3. Запасной ответ модели — на языке гостя, и о нём узнают люди.
    разработчику: list[str] = []
    стойке: list[str] = []
    виденные: set[str] = set()

    async def _разработчику(text: str, что: str) -> int:
        разработчику.append(text)
        return 1

    async def _отелю(text: str, что: str, *, corporate: bool = False) -> int:
        стойке.append(text)
        return 1

    async def _seen(_sessions, channel: str, message_id: str) -> bool:
        ключ = f"{channel}:{message_id}"
        if ключ in виденные:
            return True
        виденные.add(ключ)
        return False

    async def _нет_модели(payload, headers, **_kw):  # noqa: ANN001
        raise RuntimeError("HTTP 529: Overloaded")

    async def _факты(_settings, force: bool = False):  # noqa: ANN001
        return {"hotel": {}, "policy": {}, "rooms": [{"slug": "comfort", "name": "Comfort",
                                                       "price": 45000, "capacity": 2}]}

    отправлено: list[tuple[str, str]] = []

    class _Канал:
        def __init__(self, *_a, **_k) -> None:
            pass

        async def send(self, chat_id: str, text: str) -> str:
            отправлено.append((chat_id, text))
            return "ok"

        async def download(self, url: str) -> bytes:
            return b"image"

    settings = _gs()
    было = (settings.anthropic_api_key, _c._call_model, _c.load_facts, _dl.seen_before,
            _nt.tell_developer, _nt._tell_hotel, _fl.seen_before, _fl.guest_texts,
            _fl.read_document, _fl.match_and_apply)
    settings.anthropic_api_key = "k"
    _c._call_model, _c.load_facts, _dl.seen_before = _нет_модели, _факты, _seen
    _nt.tell_developer, _nt._tell_hotel = _разработчику, _отелю
    try:
        джеймс = {"phone": "+447542253459", "name": "James", "chat_id": "447542253459@c.us"}
        r1 = await _c.answer(settings, message="Do I have a booking for today then?",
                             history=[], today="2026-10-05", guest=джеймс)
        check("запасной ответ англоязычному гостю — по-английски",
              not r1["ok"] and not кириллица.search(r1["text"]), r1["text"][:80])
        r2 = await _c.answer(settings, message="6359909102",
                             history=[{"role": "user", "content": "It’s for today"},
                                      {"role": "assistant", "content": "Thank you."}],
                             today="2026-10-05", guest=джеймс)
        check("и на номер брони цифрами — по-английски", not кириллица.search(r2["text"]),
              r2["text"][:80])
        r3 = await _c.answer(settings, message="Есть номер на завтра?", history=[],
                             today="2026-10-05",
                             guest={"phone": "+77010000000", "chat_id": "77010000000@c.us"})
        check("русскому гостю — по-русски", r3["text"] == _c.FALLBACK, r3["text"][:80])
        check("разработчик узнаёт о запасном ответе вместе с причиной",
              any("529" in t for t in разработчику), str(разработчику)[:160])
        check("разработчику — раз в час на вид причины, а не на каждое сообщение",
              len(разработчику) == 1, str(len(разработчику)))
        check("стойка узнаёт, что гостю надо ответить самим",
              any("447542253459" in t and "ответьте" in t for t in стойке), str(стойке)[:160])
        check("стойке — раз в час на гостя",
              sum("447542253459" in t for t in стойке) == 1, str(len(стойке)))

        # Пометка о языке ставится и тогда, когда в сообщении одни цифры.
        запросы: list[dict] = []

        async def _модель(payload, headers, **_kw):  # noqa: ANN001
            запросы.append(payload)
            return {"content": [{"type": "text", "text": "Thank you."}], "stop_reason": "end_turn",
                    "usage": {}}

        _c._call_model = _модель
        await _c.answer(settings, message="6359909102",
                        history=[{"role": "user", "content": "It’s for today"},
                                 {"role": "assistant", "content": "Thank you."}],
                        today="2026-10-05", guest=джеймс)
        последняя = запросы[-1]["messages"][-1]["content"] if запросы else ""
        текст = " ".join(b.get("text", "") for b in последняя) if isinstance(последняя, list) else str(последняя)
        check("номер брони цифрами получает пометку «гость пишет не по-русски»",
              "НЕ по-русски" in текст, текст[:120])

        # 4. Снимки и файлы: один ответ на несколько подряд, на языке гостя,
        # а стойка правда получает сообщение.
        стойке.clear()

        async def _истории(_sessions, _channel, _chat, limit: int = 6):  # noqa: ANN001
            return ["Do I have a booking for today then?"]

        async def _не_платёжка(_settings, _data, _name):  # noqa: ANN001
            return _NS(is_payment=False, summary="")

        _fl.seen_before, _fl.guest_texts, _fl.read_document = _seen, _истории, _не_платёжка
        снимок = _parse({"typeWebhook": "incomingMessageReceived", "idMessage": f"IMG-{_t.time()}",
                         "senderData": {"chatId": "447542253459@c.us", "senderName": "James"},
                         "messageData": {"typeMessage": "imageMessage", "fileMessageData": {
                             "downloadUrl": "https://example/1.jpg", "fileName": "1.jpg"}}})
        ответы = [await _fl.handle_file(settings, None, _Канал(), снимок) for _ in range(3)]
        check("на три снимка подряд — один ответ, а не три",
              sum(bool(r.text) for r in ответы) == 1, str([r.text[:30] for r in ответы]))
        check("ответ на снимок — по-английски",
              bool(ответы[0].text) and not кириллица.search(ответы[0].text), ответы[0].text[:80])
        check("стойка узнаёт о снимке, и один раз",
              sum("файл" in t for t in стойке) == 1, str(стойке)[:160])

        # Платёжка, которую не засчитать автоматически: обещание «менеджер
        # проверит» теперь выполняется — стойка получает сообщение.
        стойке.clear()

        async def _платёжка(_settings, _data, _name):  # noqa: ANN001
            return _NS(is_payment=True)

        async def _на_проверку(_booking, _doc, facts=None):  # noqa: ANN001
            return _NS(verdict="needs_manager", reason="сумма не совпала", booking_ref="",
                       applied_amount=0)

        _fl.read_document, _fl.match_and_apply = _платёжка, _на_проверку
        чек = _parse({"typeWebhook": "incomingMessageReceived", "idMessage": f"PAY-{_t.time()}",
                      "senderData": {"chatId": "447542253459@c.us", "senderName": "James"},
                      "messageData": {"typeMessage": "documentMessage", "fileMessageData": {
                          "downloadUrl": "https://example/r.pdf", "fileName": "r.pdf"}}})
        ответ = await _fl.handle_file(settings, None, _Канал(), чек)
        check("платёжка на проверку — ответ по-английски",
              not кириллица.search(ответ.text), ответ.text[:80])
        check("и стойка правда получает её на проверку",
              any("проверить вручную" in t for t in стойке), str(стойке)[:160])

        # 5. Пустой ответ (второй снимок подряд) в WhatsApp не уходит.
        from httpx import ASGITransport  # noqa: PLC0415

        from app.main import app as _app  # noqa: PLC0415

        было_канал, было_ответ = _wh.WhatsAppChannel, _wh.reply_for
        отправлено.clear()

        async def _пусто(*_a, **_k):  # noqa: ANN002, ANN003
            return _fl.Reply("")

        _wh.WhatsAppChannel, _wh.reply_for = _Канал, _пусто
        try:
            async with httpx.AsyncClient(transport=ASGITransport(app=_app), base_url="http://qa") as cl:
                ответ_вебхука = await cl.post(
                    "/api/webhooks/whatsapp",
                    headers={"X-Api-Key": settings.whatsapp_webhook_secret},
                    json={"typeWebhook": "incomingMessageReceived", "idMessage": f"EMPTY-{_t.time()}",
                          "senderData": {"chatId": "447542253459@c.us", "senderName": "James"},
                          "messageData": {"typeMessage": "imageMessage", "fileMessageData": {
                              "downloadUrl": "https://example/2.jpg", "fileName": "2.jpg"}}})
        finally:
            _wh.WhatsAppChannel, _wh.reply_for = было_канал, было_ответ
        check("пустой ответ гостю не отправляется", ответ_вебхука.status_code == 200 and not отправлено,
              f"HTTP {ответ_вебхука.status_code} {отправлено[:1]}")
    finally:
        (settings.anthropic_api_key, _c._call_model, _c.load_facts, _dl.seen_before,
         _nt.tell_developer, _nt._tell_hotel, _fl.seen_before, _fl.guest_texts,
         _fl.read_document, _fl.match_and_apply) = было

    # 6. Дожим пишет на языке гостя.
    system_prompts: list[str] = []
    настоящий = _fu.httpx.AsyncClient

    def _отвечает(request: httpx.Request) -> httpx.Response:
        import json as _json  # noqa: PLC0415

        system_prompts.append(str(_json.loads(request.content).get("system")))
        return httpx.Response(200, json={"content": [{"type": "text", "text":
                                                      '{"write": false, "why": "qa", "text": ""}'}]})

    было_ключ = settings.anthropic_api_key
    settings.anthropic_api_key = "k"
    _fu.httpx.AsyncClient = lambda **kw: настоящий(
        transport=httpx.MockTransport(_отвечает), **{k: v for k, v in kw.items() if k != "transport"})
    try:
        await _fu._decide(settings, [{"role": "Гость", "text": "Is it free on Friday?"}], 5, 1,
                          "бриф", "en")
    finally:
        _fu.httpx.AsyncClient = настоящий
        settings.anthropic_api_key = было_ключ
    check("дожим англоязычному гостю просит писать по-английски",
          bool(system_prompts) and "по-английски (English)" in system_prompts[-1])
    import inspect as _insp  # noqa: PLC0415

    check("дожим определяет язык гостя по переписке",
          "guest_language(" in _insp.getsource(_fu.plan))

    # 7. Лимит запросов: ждём столько, сколько просит сервер, но не дольше 20 секунд.
    паузы: list[float] = []

    class _Шим:
        @staticmethod
        async def sleep(секунд: float) -> None:
            паузы.append(секунд)

    for просит, ждём in (("7", 7.0), ("120", 20.0)):
        паузы.clear()
        очередь = [httpx.Response(429, headers={"retry-after": просит}, text="rate_limit_error"),
                   httpx.Response(200, json={"content": [], "stop_reason": "end_turn"})]
        было_asyncio = _c.asyncio
        _c.asyncio = _Шим
        try:
            await _c._call_model({"model": "m"}, {}, transport=httpx.MockTransport(
                lambda request: очередь.pop(0)))
        finally:
            _c.asyncio = было_asyncio
        check(f"retry-after {просит} → пауза {ждём:g} с", паузы == [ждём], str(паузы))

    # Сервер раз за разом просит ждать по 20 секунд — сдаёмся раньше минуты.
    паузы.clear()
    было_asyncio = _c.asyncio
    _c.asyncio = _Шим
    try:
        await _c._call_model({"model": "m"}, {}, transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"retry-after": "20"}, text="rate")))
        сдались = False
    except RuntimeError:
        сдались = True
    finally:
        _c.asyncio = было_asyncio
    check("всего пауз за ответ — не больше 25 секунд", сдались and sum(паузы) <= 25, str(паузы))


async def qa_staff_images_facts() -> None:
    """Сотрудник в чате, снимки брони и факты от отеля.

    2026-10-05: ресепшн и бот отвечали гостю наперебой («Sorry, AI answering
    faster than me»); на скриншоты Booking.com бот ответил «не платёжный
    документ»; про диван-кровать, багаж и парковку справка молчала.
    """
    head("Сотрудник в чате, снимки брони, факты от отеля")

    import time as _t  # noqa: PLC0415
    from types import SimpleNamespace as _NS  # noqa: PLC0415

    from httpx import ASGITransport  # noqa: PLC0415

    import app.channels.flow as _fl  # noqa: PLC0415
    import app.followup as _fu  # noqa: PLC0415
    import app.webhooks_api as _wh  # noqa: PLC0415
    from app.channels.whatsapp import parse_staff  # noqa: PLC0415
    from app.concierge import FIRST_ACTION, _guest_texts  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415
    from app.dialogs import guest_texts, load_history, remember_staff, staff_active  # noqa: PLC0415
    from app.knowledge import render_brief  # noqa: PLC0415
    from app.main import app as _app  # noqa: PLC0415
    from app.payment_docs import PaymentDoc, check_recipient  # noqa: PLC0415

    settings = _gs()
    чат = f"44{int(_t.time() * 1000) % 10_000_000_000:010d}@c.us"

    # Сотрудник сам начинает разговор («сообщите время приезда») — бот не
    # уступает: гость ответит, когда смены уже не будет.
    чат_рассылки = f"44{int(_t.time() * 1000 + 3) % 10_000_000_000:010d}@c.us"
    from app.dialogs import remember_staff as _rs, guest_wrote_recently as _gwr  # noqa: PLC0415

    check("гость ещё не писал — разговор начинает сотрудник",
          not await _gwr(SessionLocal, "whatsapp", чат_рассылки))
    await _rs(SessionLocal, "whatsapp", чат_рассылки, "Dear Guest, please let us know your arrival time",
              pauses_bot=False)
    check("на рассылку сотрудника бот не замолкает",
          not await staff_active(SessionLocal, "whatsapp", чат_рассылки, 60))
    async with SessionLocal() as ses:
        check("но дожим туда всё равно не пишет", await _fu._staff_spoke(ses, чат_рассылки))

    # 1. Сообщение с телефона отеля — сотрудник.
    исходящее = {"typeWebhook": "outgoingMessageReceived", "idMessage": f"STAFF-{_t.time()}",
                 "senderData": {"chatId": чат, "sender": "77003002526@c.us"},
                 "messageData": {"typeMessage": "textMessage",
                                 "textMessageData": {"textMessage": "Yes, your room has a sofa bed"}}}
    разбор = parse_staff(исходящее)
    check("сообщение с телефона отеля распознано как ответ сотрудника",
          разбор is not None and разбор.chat_id == чат and "sofa bed" in разбор.text)
    check("входящее от гостя сотрудником не считается",
          parse_staff({**исходящее, "typeWebhook": "incomingMessageReceived"}) is None)
    check("ответы бота через API сотрудником не считаются",
          parse_staff({**исходящее, "typeWebhook": "outgoingAPIMessageReceived"}) is None)

    отправлено: list[tuple[str, str]] = []
    вызван_ответ: list[str] = []

    class _Канал:
        def __init__(self, *_a, **_k) -> None:
            pass

        async def send(self, chat_id: str, text: str) -> str:
            отправлено.append((chat_id, text))
            return "ok"

    async def _ответ(_settings, _booking, _channel, message):  # noqa: ANN001
        вызван_ответ.append(message.text)
        return _fl.Reply("Hello!")

    from app.dialogs import remember_guest as _rg  # noqa: PLC0415

    await _rg(SessionLocal, "whatsapp", чат, "It has a sofa bed too, right?")
    было = (_wh.WhatsAppChannel, _wh.reply_for)
    _wh.WhatsAppChannel, _wh.reply_for = _Канал, _ответ
    ключ = {"X-Api-Key": settings.whatsapp_webhook_secret}
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=_app), base_url="http://qa") as cl:
            r = await cl.post("/api/webhooks/whatsapp", headers=ключ, json=исходящее)
            check("вебхук принимает ответ сотрудника", r.status_code == 200 and r.json().get("staff"),
                  r.text[:100])
            check("и бот знает, что в чате человек",
                  await staff_active(SessionLocal, "whatsapp", чат, settings.staff_pause_minutes))
            r = await cl.post("/api/webhooks/whatsapp", headers=ключ, json={
                "typeWebhook": "incomingMessageReceived", "idMessage": f"G1-{_t.time()}",
                "senderData": {"chatId": чат, "senderName": "James"},
                "messageData": {"typeMessage": "textMessage",
                                "textMessageData": {"textMessage": "Great, thank you!"}}})
            check("пока сотрудник в чате, бот молчит",
                  r.status_code == 200 and not отправлено and not вызван_ответ, r.text[:100])
            from sqlalchemy import select as _select  # noqa: PLC0415

            from app.db import DialogMessage as _DM  # noqa: PLC0415

            async with SessionLocal() as ses:
                история = [row.content for row in (await ses.execute(
                    _select(_DM).where(_DM.chat_id == чат).order_by(_DM.id))).scalars().all()]
            check("слова сотрудника и реплика гостя легли в историю",
                  any("sofa bed" in str(c) for c in история)
                  and any("Great, thank you" in str(c) for c in история), str(история)[:160])

            было_пауза = settings.staff_pause_minutes
            settings.staff_pause_minutes = 0
            try:
                r = await cl.post("/api/webhooks/whatsapp", headers=ключ, json={
                    "typeWebhook": "incomingMessageReceived", "idMessage": f"G2-{_t.time()}",
                    "senderData": {"chatId": чат, "senderName": "James"},
                    "messageData": {"typeMessage": "textMessage",
                                    "textMessageData": {"textMessage": "One more question"}}})
            finally:
                settings.staff_pause_minutes = было_пауза
            check("сотрудник замолчал — бот снова отвечает", bool(вызван_ответ) and bool(отправлено),
                  r.text[:100])
    finally:
        _wh.WhatsAppChannel, _wh.reply_for = было

    async with SessionLocal() as ses:
        check("дожим не пишет туда, где разговор вёл сотрудник", await _fu._staff_spoke(ses, чат))
    check("в истории для модели сказанное сотрудником помечено",
          any(str(c).startswith("[Ответил сотрудник отеля]") for c in история))

    # 2. Снимок брони — в разговор, на языке гостя.
    переданное: list[tuple[str, str]] = []

    async def _прочитан(_settings, _data, _name):  # noqa: ANN001
        return _NS(is_payment=False, summary="Подтверждение брони Booking.com: James Gibson, "
                   "AIRIS Residence, 5–6 октября 2026, Superior Double Room, 3 взрослых")

    async def _текст(_settings, _booking, message, *, language: str = ""):  # noqa: ANN001
        переданное.append((message.text, language))
        return _fl.Reply("I can see your booking.")

    async def _истории(_sessions, _channel, _chat, limit: int = 6):  # noqa: ANN001
        return ["Do I have a booking for today then?"]

    class _Скачать:
        async def download(self, url: str) -> bytes:
            return b"image"

    было = (_fl.read_document, _fl.handle_text, _fl.guest_texts)
    _fl.read_document, _fl.handle_text, _fl.guest_texts = _прочитан, _текст, _истории
    try:
        снимок = _parse({"typeWebhook": "incomingMessageReceived", "idMessage": f"IMG-{_t.time()}",
                         "senderData": {"chatId": "447542253459@c.us", "senderName": "James"},
                         "messageData": {"typeMessage": "imageMessage", "fileMessageData": {
                             "downloadUrl": "https://example/b.jpg", "fileName": "b.jpg"}}})
        ответ = await _fl.handle_file(settings, None, _Скачать(), снимок)
    finally:
        _fl.read_document, _fl.handle_text, _fl.guest_texts = было
    check("снимок брони уходит в разговор с тем, что на нём",
          bool(переданное) and переданное[0][0].startswith("[Гость прислал снимок. На нём:")
          and "Superior Double Room" in переданное[0][0], str(переданное)[:160])
    check("и язык гостя передаётся вместе с ним — английский",
          bool(переданное) and переданное[0][1] == "en", str(переданное)[:80])
    check("гость получает ответ консьержа, а не «не платёжный документ»",
          ответ.text == "I can see your booking.")
    check("в правилах — что делать со снимком брони", "[Гость прислал снимок" in FIRST_ACTION)
    check("и что делать, когда сказали «оплатили»", "оплатили переводом" in FIRST_ACTION)

    # Служебные пометки по-русски не сбивают язык гостя.
    чат2 = f"44{int(_t.time() * 1000 + 7) % 10_000_000_000:010d}@c.us"
    await save_turn_qa(чат2, [{"role": "user", "content": "Do I have a booking?"},
                              {"role": "assistant", "content": "Yes."},
                              {"role": "user", "content": "[Гость прислал снимок. На нём: бронь]"},
                              {"role": "assistant", "content": "Thanks."}])
    check("служебная пометка не считается репликой гостя (база)",
          await guest_texts(SessionLocal, "whatsapp", чат2) == ["Do I have a booking?"])
    check("и в истории разговора тоже",
          _guest_texts([{"role": "user", "content": "Hi there"},
                        {"role": "user", "content": "[Гость прислал снимок. На нём: бронь]"}])
          == ["Hi there"])

    # 3. Факты от отеля в справке консьержа.
    факты = {
        "hotel": {"name": "Airis", "legal": {"iik": "KZ11722S000048166255", "currencyAccounts": {
            "USD": "KZ73551E129373278USD", "EUR": "KZ78551E129377576EUR"}}},
        "policy": {"luggage": "да, храним багаж гостей на стойке — до заезда и после выезда"},
        "conciergeNotes": ["Comfort Plus на Booking.com называется «Superior Double Room»."],
        "faq": [{"q": "Есть ли парковка?", "a": "Да, у отеля круглосуточная парковка под видеонаблюдением."}],
    }
    бриф = render_brief(факты)
    check("справка знает, что багаж храним", "Хранение багажа: да, храним" in бриф)
    check("справка знает название номера на Booking.com", "Superior Double Room" in бриф)
    check("валютные счета — в справке", "USD — KZ73551E129373278USD" in бриф
          and "EUR — KZ78551E129377576EUR" in бриф)
    check("и правило: после «оплатили» — менеджеру", "front_desk_request" in бриф.split("ВАЛЮТНЫЕ")[-1])

    # Перевод на валютный счёт — не «чужой счёт».
    чек = PaymentDoc(is_payment=True, payee_account="KZ73551E129373278USD")
    вердикт, _ = check_recipient(чек, факты)
    check("перевод на долларовый счёт отеля признаётся своим", вердикт == "ok", вердикт)
    чужой, _ = check_recipient(PaymentDoc(is_payment=True, payee_account="KZ00999X000000123456"), факты)
    check("а чужой счёт — по-прежнему чужой", чужой == "mismatch", чужой)


async def save_turn_qa(chat_id: str, messages: list[dict]) -> None:
    from app.dialogs import save_turn  # noqa: PLC0415

    await save_turn(SessionLocal, "whatsapp", chat_id, messages, 0)


async def qa_price_sync() -> None:
    """Цены на сайте — как в Exely, по ближайшей продаваемой дате.

    2026-10-05: прайс ресепшена, Exely и сайт показывали разные цены. Владелец
    решил, что сайт берёт цены из Exely. Цены в Exely сезонные (одноместный в
    октябре 35 000, с ноября 25 000), поэтому берётся ближайшая дата.
    """
    head("Цены сайта из Exely")

    from datetime import date as _d, timedelta as _td  # noqa: PLC0415
    from types import SimpleNamespace as _NS  # noqa: PLC0415
    import inspect as _insp  # noqa: PLC0415

    from sqlalchemy import delete as _del  # noqa: PLC0415

    import app.webhooks_api as _wh  # noqa: PLC0415
    from app.db import Room as _Room  # noqa: PLC0415
    from app.price_sync import base_price, exely_prices, sync_prices  # noqa: PLC0415

    check("обычная цена — прежняя у тарифа со скидкой",
          base_price([{"price": 45000, "was": 50000}, {"price": 50000}]) == 50000)
    check("тарифы объектами тоже читаются",
          base_price([_NS(price=31500, was=35000), _NS(price=33129, was=None)]) == 35000)
    check("скидок нет — самый дорогой тариф", base_price([{"price": 30000}, {"price": 32000}]) == 32000)
    check("продано — цены нет", base_price(()) is None)

    сегодня = _d(2026, 10, 5)
    # QA-номер: на 1-й день продан, на 4-й — 30 000 / 33 000, на 7-й (новый
    # сезон) — 20 000. Ближайшая продаваемая дата — 4-й день.
    def _offer(slug, price):  # noqa: ANN001, ANN202
        rates = (_NS(price=price - 1000, was=price),) if price else ()
        return _NS(room_slug=slug, rates=rates)

    class _Exely:
        async def availability(self, check_in, check_out, *, guests=2):  # noqa: ANN001
            день = (check_in - сегодня).days
            if день < 4:
                return _NS(offers=[_offer("qa-price-room", None), _offer("qa-price-single", None)])
            if день < 7:
                return _NS(offers=[_offer("qa-price-room", 30000 if guests == 1 else 33000),
                                   _offer("qa-price-single", 25000 if guests == 1 else None)])
            return _NS(offers=[_offer("qa-price-room", 20000), _offer("qa-price-single", 15000)])

    цены = await exely_prices(_Exely(), сегодня)
    check("цена — на ближайшую продаваемую дату, а не следующего сезона",
          цены.get("qa-price-room") == {1: 30000, 2: 33000}, str(цены.get("qa-price-room")))

    async with SessionLocal() as ses:
        await ses.execute(_del(_Room).where(_Room.slug.in_(["qa-price-room", "qa-price-single"])))
        ses.add(_Room(slug="qa-price-room", name="QA", short_name="QA", price=1, price_double=0,
                      area="1 м²", capacity=2, is_published=False))
        ses.add(_Room(slug="qa-price-single", name="QA1", short_name="QA1", price=1, price_double=0,
                      area="1 м²", capacity=1, is_published=False))
        await ses.commit()
    try:
        async with SessionLocal() as ses:
            проба = await sync_prices(ses, _Exely(), today=сегодня, dry_run=True)
        async with SessionLocal() as ses:
            номер = await ses.get(_Room, (await ses.execute(
                __import__("sqlalchemy").select(_Room.id).where(_Room.slug == "qa-price-room"))).scalar())
            check("пробный прогон ничего не меняет", номер.price == 1 and bool(проба["changes"]),
                  str(проба["changes"])[:120])
        async with SessionLocal() as ses:
            итог = await sync_prices(ses, _Exely(), today=сегодня)
        async with SessionLocal() as ses:
            rows = {r.slug: r for r in (await ses.execute(__import__("sqlalchemy").select(_Room).where(
                _Room.slug.in_(["qa-price-room", "qa-price-single"])))).scalars()}
        check("цена за одного и за двоих — как в Exely",
              (rows["qa-price-room"].price, rows["qa-price-room"].price_double) == (30000, 33000),
              str((rows["qa-price-room"].price, rows["qa-price-room"].price_double)))
        check("у одноместного цена за двоих та же, что за одного",
              (rows["qa-price-single"].price, rows["qa-price-single"].price_double) == (25000, 25000))
        async with SessionLocal() as ses:
            повтор = await sync_prices(ses, _Exely(), today=сегодня)
        check("повторный прогон ничего не меняет", not повтор["changes"], str(повтор["changes"])[:100])

        class _Молчит:
            async def availability(self, *_a, **_k):  # noqa: ANN002, ANN003
                return _NS(offers=[])

        async with SessionLocal() as ses:
            пусто = await sync_prices(ses, _Молчит(), today=сегодня)
        check("Exely не отдал цен — на сайте ничего не трогаем", not пусто["ok"])
    finally:
        async with SessionLocal() as ses:
            await ses.execute(_del(_Room).where(_Room.slug.in_(["qa-price-room", "qa-price-single"])))
            await ses.commit()

    check("точка переноса цен защищена ключом",
          "_presented(request) != secret" in _insp.getsource(_wh.sync_prices_endpoint))
    import pathlib as _pl  # noqa: PLC0415

    check("перенос цен запускается каждый день",
          "sync-prices" in (_pl.Path(__file__).parent.parent / ".github/workflows/daily-check.yml")
          .read_text(encoding="utf-8"))


async def qa_site_reviews() -> None:
    """Отзывы с сайта: хранятся, выходят после проверки, спам не проходит."""
    head("Отзывы с сайта")

    import time as _t  # noqa: PLC0415

    from httpx import ASGITransport  # noqa: PLC0415

    import app.notify as _nt  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415
    from app.main import app as _app  # noqa: PLC0415

    settings = _gs()
    отелю: list[str] = []

    async def _отелю(text: str, что: str, *, corporate: bool = False) -> int:
        отелю.append(text)
        return 1

    было = _nt._tell_hotel
    _nt._tell_hotel = _отелю
    ip = f"10.{int(_t.time()) % 250}.{int(_t.time() * 7) % 250}.1"
    гость = {"X-Forwarded-For": ip}
    метка = f"QA-отзыв-{int(_t.time())}"
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=_app), base_url="http://qa") as cl:
            r = await cl.post("/api/reviews", headers=гость, json={
                "name": "Пётр", "text": f"{метка}: чисто, тихо, отличный завтрак", "stars": 5,
                "stay": "сентябрь 2026", "contact": "+77010000000"})
            check("отзыв принимается", r.status_code == 201, r.text[:100])
            check("отель узнаёт о новом отзыве", any(метка in t for t in отелю))
            публичные = (await cl.get("/api/reviews")).json()
            check("до проверки на сайте его нет", not any(метка in x["text"] for x in публичные))

            r = await cl.post("/api/reviews", headers=гость, json={
                "name": "Bot", "text": "buy cheap stuff here now", "stars": 5, "website": "http://spam"})
            check("бот с заполненной ловушкой не сохраняется", r.status_code == 201 and "id" not in r.json())
            r = await cl.post("/api/reviews", headers=гость, json={"name": "П", "text": "ok", "stars": 9})
            check("пустой и кривой отзыв отклоняется", r.status_code == 422)

            check("админка отзывов закрыта без входа", (await cl.get("/api/admin/reviews")).status_code in (401, 403))
            вход = await cl.post("/api/auth/login", json={"username": settings.admin_username,
                                                          "password": settings.admin_password})
            токен = (вход.json() if вход.status_code == 200 else {}).get("token")
            check("сотрудник входит в админку", bool(токен), f"HTTP {вход.status_code}")
            if токен:
                шапка = {"Authorization": f"Bearer {токен}"}
                все = (await cl.get("/api/admin/reviews", headers=шапка)).json()
                мой = next((x for x in все if метка in x["text"]), None)
                check("в админке отзыв виден с контактом", мой is not None and мой["contact"] == "+77010000000")
                if мой:
                    await cl.patch(f"/api/admin/reviews/{мой['id']}", headers=шапка, json={"status": "published"})
                    публичные = (await cl.get("/api/reviews")).json()
                    на_сайте = next((x for x in публичные if метка in x["text"]), None)
                    check("после публикации отзыв на сайте", на_сайте is not None)
                    check("контакт гостя на сайт не попадает", на_сайте is not None and "contact" not in на_сайте)
                    await cl.delete(f"/api/admin/reviews/{мой['id']}", headers=шапка)

            коды = [(await cl.post("/api/reviews", headers=гость, json={
                "name": "Пётр", "text": "ещё один отзыв подряд", "stars": 4})).status_code for _ in range(3)]
            check("много отзывов с одного адреса — стоп", 429 in коды, str(коды))
    finally:
        _nt._tell_hotel = было
        from sqlalchemy import delete as _del  # noqa: PLC0415

        from app.db import SiteReview as _SR  # noqa: PLC0415

        async with SessionLocal() as ses:
            await ses.execute(_del(_SR).where(_SR.ip == ip))
            await ses.commit()


async def qa_nearest_and_style() -> None:
    """Нет мест на даты гостя — бот сам находит ближайшие; ответы короткие.

    2026-10-07 гость писал по-казахски про 14–17 октября. Бот сказал правду
    (все три ночи подряд ни в одной категории не свободны), но трижды
    переспросил гостя вместо того, чтобы предложить 17–20 — оно было
    свободно в трёх категориях. Гость написал «позвоню» и ушёл. И ответы
    были длиннее вопросов: на два слова — два предложения с извинением.
    """
    head("Ближайшие даты и короткий стиль")

    import asyncio as _aio  # noqa: PLC0415
    from datetime import date as _d, timedelta as _td  # noqa: PLC0415

    import app.almaty as _al  # noqa: PLC0415
    import app.concierge as _c  # noqa: PLC0415
    import app.nearest as _nr  # noqa: PLC0415
    from app.booking_system.base import Availability as _Av, RatePlan as _Rate, RoomOffer as _Offer  # noqa: PLC0415

    сегодня = _d(2026, 10, 7)
    # Свободно по ночам: ночь → {категория: (сколько, цена)}. 14 и 15-го — по
    # одному номеру в разных категориях, 16-го всё занято, с 17-го свободно.
    таблица = {
        _d(2026, 10, 14): {"comfort": (1, 42000)},
        _d(2026, 10, 15): {"standart": (1, 35000)},
        _d(2026, 10, 17): {"comfort-plus": (1, 47250), "apart": (1, 45000)},
        _d(2026, 10, 18): {"comfort-plus": (1, 47250), "apart": (1, 45000)},
        _d(2026, 10, 19): {"comfort-plus": (2, 47250), "apart": (1, 45000)},
        _d(2026, 10, 20): {"comfort-plus": (2, 47250)},
        _d(2026, 10, 21): {"comfort-plus": (2, 47250)},
    }
    вызовов = {"n": 0}
    имена = {"comfort": "Comfort", "standart": "Standart", "comfort-plus": "Comfort Plus", "apart": "Apart"}

    class _Система:
        async def availability(self, check_in, check_out, *, guests=2):  # noqa: ANN001
            вызовов["n"] += 1
            ночи = [check_in + _td(days=n) for n in range((check_out - check_in).days)]
            общие = None
            for ночь in ночи:
                cats = set(таблица.get(ночь, {}))
                общие = cats if общие is None else общие & cats
            offers = []
            for slug, name in имена.items():
                if общие and slug in общие:
                    price = min(таблица[н][slug][1] for н in ночи)
                    offers.append(_Offer(room_slug=slug, room_name=name, rooms_left=1,
                                         price_per_night=price, source="exely",
                                         rates=(_Rate(code="r", name="Тариф", price=price),)))
                else:
                    offers.append(_Offer(room_slug=slug, room_name=name, rooms_left=0,
                                         price_per_night=None, source="exely"))
            return _Av(check_in, check_out, len(ночи), offers, "exely")

    система = _Система()
    варианты = await _nr.nearest_options(система, _d(2026, 10, 14), _d(2026, 10, 17), 2, сегодня)
    check("ближайшее окно — 17–20 октября, три ночи",
          bool(варианты) and варианты[0].check_in == _d(2026, 10, 17) and варианты[0].nights == 3,
          str([(o.check_in, o.nights) for o in варианты]))
    check("в нём свободны именно те категории, что есть",
          bool(варианты) and set(варианты[0].rooms) == {"comfort-plus", "apart"}, str(варианты[:1]))
    check("цена — самая низкая из тарифов",
          bool(варианты) and варианты[0].rooms["apart"][1] == 45000)
    check("не больше двух вариантов, и не копии соседних дней",
          len(варианты) <= 2 and all(abs((a.check_in - b.check_in).days) >= 2
                                      for a in варианты for b in варианты if a is not b),
          str([(o.check_in, o.nights) for o in варианты]))
    check("прошедшие даты не предлагаются",
          all(o.check_in >= сегодня for o in await _nr.nearest_options(
              система, _d(2026, 10, 8), _d(2026, 10, 10), 2, сегодня)))

    # На ночь-две короче, если такого же периода нет.
    таблица_было = dict(таблица)
    таблица.clear()
    таблица.update({_d(2026, 10, 14): {"comfort": (1, 42000)}, _d(2026, 10, 15): {"comfort": (1, 42000)}})
    короче = await _nr.nearest_options(система, _d(2026, 10, 14), _d(2026, 10, 17), 2, сегодня)
    check("нет окна той же длины — предлагается короче (2 ночи из 3)",
          bool(короче) and короче[0].nights == 2 and короче[0].check_in == _d(2026, 10, 14),
          str([(o.check_in, o.nights) for o in короче]))
    таблица.clear()
    пусто = await _nr.nearest_options(система, _d(2026, 10, 14), _d(2026, 10, 17), 2, сегодня)
    check("рядом ничего нет — пустой список, а не выдумка", пусто == [])
    таблица.update(таблица_было)

    class _Тормоз:
        async def availability(self, *_a, **_k):  # noqa: ANN002, ANN003
            await _aio.sleep(60)

    было_предел = _nr.TIME_LIMIT
    _nr.TIME_LIMIT = 0.2
    try:
        медленно = await _nr.nearest_options(_Тормоз(), _d(2026, 10, 14), _d(2026, 10, 17), 2, сегодня)
    finally:
        _nr.TIME_LIMIT = было_предел
    check("медленная система — поиск сдаётся, гость не ждёт", медленно == [])

    # В самом инструменте.
    было_today = _al.today
    _al.today = lambda: сегодня
    try:
        вызовов["n"] = 0
        текст = await _c._tool_availability(
            система, {"check_in": "2026-10-14", "check_out": "2026-10-17", "guests": 2}, None)
        check("в ответе инструмента — ближайшее свободное",
              "2026-10-17 — 2026-10-20" in текст and "Apart" in текст, текст[-400:])
        check("и просьба предложить его одной короткой фразой",
              "ОДНОЙ короткой фразой" in текст and "Не проси гостя самому искать даты" in текст)
        check("в подсказке нет русских слов-образцов, которые модель копирует",
              "подойдёт" not in текст.lower() and "на языке гостя" in текст)
        check("к результату инструмента для казаха — напоминание о языке",
              "по-казахски, не по-русски" in _c._с_языком(текст, "kk")
              and "по-английски" in _c._с_языком(текст, "en"))
        check("русскому гостю результат инструмента не меняется", _c._с_языком(текст, "ru") == текст)
        check("история, начатая с ответа инструмента, открывается",
              _c._открывается([{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x",
                                                            "content": "ок"}]},
                               {"role": "user", "content": "Привет"}])[0]["content"] == "Привет")
        вызовов["n"] = 0
        свободно = await _c._tool_availability(
            система, {"check_in": "2026-10-17", "check_out": "2026-10-20", "guests": 2}, None)
        check("когда места есть, лишних запросов не делается",
              вызовов["n"] == 1 and "ближайш" not in свободно.lower())
        корп = await _c._tool_availability(
            система, {"check_in": "2026-10-14", "check_out": "2026-10-17", "guests": 2}, None,
            corporate={"company": "ТОО", "rates": {}, "discount_percent": 0})
        check("корпоративному гостю прайсовые цены вариантов не называются",
              "тенге за ночь" not in корп.split("проверено тем же запросом")[-1], корп[-300:])
        таблица.clear()
        нет = await _c._tool_availability(
            система, {"check_in": "2026-10-14", "check_out": "2026-10-17", "guests": 2}, None)
        check("рядом пусто — подсказка про стойку остаётся",
              "стойк" in нет.lower() and "ничего не нашёл" in нет)
        таблица.update(таблица_было)
    finally:
        _al.today = было_today

    # Стиль: длина ответа по длине сообщения.
    check("два слова — одна короткая фраза", "ОДНОЙ короткой фразой" in _c._style_note("Барма нөмір"))
    check("пять-двенадцать слов — одно-два предложения",
          "одним-двумя короткими" in _c._style_note("Нам нужен номер на двоих с четырнадцатого"))
    check("длинное сообщение — без пометки",
          _c._style_note("Здравствуйте, хотели бы забронировать номер на три ночи с двадцатого, "
                         "нас двое взрослых") == "")
    check("служебная реплика про снимок по длине не судится",
          _c._style_note("[Гость прислал снимок. На нём: бронь]") == "")
    правила = _c.build_system_prompt("", "2026-10-07", availability="exely")
    check("в правилах: длина ответа — по длине сообщения гостя", "по длине сообщения гостя" in правила)
    check("в правилах: месяц по числам не переспрашивать", "месяц не спрашивай" in правила)
    check("в правилах: «да» на «А или Б» — первый вариант", "это первый вариант" in правила)
    check("в правилах: опечатки гостя не копировать", "Не копируй опечатки" in правила)
    check("в правилах: не просить гостя искать другие даты", "не проси его назвать другие даты" in правила)
    check("в правилах: цены с пробелом и знаком тенге", "«36 000 ₸»" in правила)
    казахская = _c._language_note("Саламатсызба с14 по17", first=True, language="kk")
    check("казахская пометка: разговорный язык, «Сіз», точное приветствие",
          "на «Сіз»" in казахская and "«Сәлеметсіз бе!»" in казахская, казахская[:200])
    check("английская пометка: естественно, как администратор",
          "как живой администратор" in _c._language_note("Do you have a room?", first=True, language="en"))
    import app.followup as _fu  # noqa: PLC0415

    check("дожим — одно предложение", "до 20 слов" in _fu.DECIDE_PROMPT)


async def qa_front_desk() -> None:
    """Просьба живущего гостя — на стойку, а не в пустое «стойка подтвердит».

    2026-10-04 гость из номера 105 попросил утром переехать в другой номер.
    Бот пообещал, что стойка всё подтвердит, а стойка ничего не узнала.
    """
    head("Просьба гостя на стойку")

    import app.notify as _nt  # noqa: PLC0415
    from app.concierge import READ_ONLY_TOOLS, _tool_front_desk  # noqa: PLC0415

    check("инструмент есть в боевом наборе",
          any(t["name"] == "front_desk_request" for t in READ_ONLY_TOOLS))

    ушло: list[str] = []

    async def _отелю(text: str, что: str, *, corporate: bool = False) -> int:
        ушло.append(text)
        return 1

    было = _nt._tell_hotel
    _nt._tell_hotel = _отелю
    try:
        ответ = await _tool_front_desk(
            {"name": "tianyue", "phone": "+8615712455710", "chat_id": "8615712455710@c.us"},
            {"request": "Хочет завтра утром переехать в другой номер, выезд в обычное время",
             "room_number": "105", "urgent": True})
        текст = ушло[0] if ушло else ""
        check("стойке ушло сообщение", len(ушло) == 1)
        check("в нём суть просьбы", "переехать в другой номер" in текст, текст[:120])
        check("номер комнаты", "Живёт в номере: 105" in текст)
        check("кто и как связаться", "+8615712455710" in текст and "tianyue" in текст)
        check("пометка срочности", "Срочно" in текст)
        check("модели сказано, что передано, и без обещаний",
              "передана" in ответ and "не обещай" in ответ, ответ[:120])

        пусто = await _tool_front_desk({}, {"request": "   "})
        check("пустая просьба никуда не уходит", len(ушло) == 1 and "пустая" in пусто)
    finally:
        _nt._tell_hotel = было

    async def _не_ушло(text: str, что: str, *, corporate: bool = False) -> int:
        return 0

    _nt._tell_hotel = _не_ушло
    try:
        ответ = await _tool_front_desk({}, {"request": "полотенца"})
        check("не ушло — модель не врёт, что передала, и даёт телефон",
              "Передать не удалось" in ответ and "телефон" in ответ, ответ[:120])
    finally:
        _nt._tell_hotel = было


async def qa_empty_answer() -> None:
    """Модель промолчала после инструмента — гость не получает «позвоните».

    Модель нередко пишет ответ рядом с вызовом инструмента и после
    результата молчит. Раньше код брал текст только из последнего круга и
    отдавал гостю запасное «не могу свериться, позвоните на стойку» —
    2026-10-05 так дважды из тридцати прогонов, в том числе посреди брони.
    """
    head("Пустой ответ модели")

    import app.concierge as _c  # noqa: PLC0415
    import app.notify as _nt  # noqa: PLC0415
    from app.config import get_settings as _gs  # noqa: PLC0415

    async def _факты(_settings, force: bool = False):  # noqa: ANN001
        return {"hotel": {"name": "Airis", "url": "https://airisresidence.kz"}, "policy": {}, "rooms": []}

    async def _отелю(text: str, что: str, *, corporate: bool = False) -> int:
        return 1

    def _подмена(ответы: list[dict]):
        очередь = list(ответы)

        async def _модель(payload, headers, **kw):  # noqa: ANN001
            return очередь.pop(0) if очередь else {"stop_reason": "end_turn", "content": []}
        return _модель

    вызов = {"stop_reason": "tool_use", "content": [
        {"type": "text", "text": "Передали администратору, с вами свяжутся."},
        {"type": "tool_use", "id": "t1", "name": "front_desk_request",
         "input": {"request": "Сменить номер завтра утром", "room_number": "105"}},
    ]}
    пусто = {"stop_reason": "end_turn", "content": []}

    class _Бронь:
        """Только чтение, как боевой Exely: инструменты есть, записи нет."""
        source = "exely"

    было = (_c._call_model, _c.load_facts, _nt._tell_hotel)
    _c.load_facts, _nt._tell_hotel = _факты, _отелю
    settings = _gs()
    гость = {"name": "Гость", "phone": "+77010000000", "chat_id": "77010000099@c.us"}
    try:
        _c._call_model = _подмена([вызов, пусто, пусто])
        r = await _c.answer(settings, message="I'm in room 105, can I change rooms?", history=[],
                            today="2026-10-05", booking=_Бронь(), guest=гость)
        check("промолчала дважды — берём сказанное до инструмента",
              r.get("ok") and r.get("text") == "Передали администратору, с вами свяжутся.", r.get("text", "")[:80])

        _c._call_model = _подмена([вызов, пусто, {"stop_reason": "end_turn",
                                                   "content": [{"type": "text", "text": "Готово, передали."}]}])
        r = await _c.answer(settings, message="I'm in room 105, can I change rooms?", history=[],
                            today="2026-10-05", booking=_Бронь(), guest=гость)
        check("промолчала раз — переспросили и получили ответ", r.get("text") == "Готово, передали.",
              r.get("text", "")[:80])

        _c._call_model = _подмена([пусто, пусто])
        r = await _c.answer(settings, message="?", history=[], today="2026-10-05",
                            booking=_Бронь(), guest=гость)
        check("совсем ничего — тогда уже запасной ответ с телефоном",
              not r.get("ok") and r.get("text") == _c.FALLBACK)
    finally:
        _c._call_model, _c.load_facts, _nt._tell_hotel = было


async def qa_model_retry() -> None:
    """Модель споткнулась — пробуем ещё раз, а не отдаём гостю отказ.

    2026-10-05 один ответ из девяти ушёл запасным «не могу свериться,
    позвоните на стойку» прямо после «беру, пришлите ссылку». Повтор того
    же запроса проходил.
    """
    head("Повтор запроса к модели")

    import app.concierge as _c  # noqa: PLC0415

    def _транспорт(коды: list[int]) -> tuple[httpx.MockTransport, list[int]]:
        вызовы: list[int] = []

        def _ответ(request: httpx.Request) -> httpx.Response:
            код = коды[min(len(вызовы), len(коды) - 1)]
            вызовы.append(код)
            if код == 200:
                return httpx.Response(200, json={"content": [{"type": "text", "text": "ок"}]})
            return httpx.Response(код, json={"error": {"type": "overloaded_error"}})

        return httpx.MockTransport(_ответ), вызовы

    было = _c.ПАУЗЫ_ПОВТОРА
    _c.ПАУЗЫ_ПОВТОРА = (0.0, 0.0)
    try:
        транспорт, вызовы = _транспорт([529, 200])
        data = await _c._call_model({}, {}, transport=транспорт)
        check("перегрузка, потом успех — ответ получен",
              data.get("content", [{}])[0].get("text") == "ок" and вызовы == [529, 200], str(вызовы))

        транспорт, вызовы = _транспорт([529, 529, 529, 529])
        упало = False
        try:
            await _c._call_model({}, {}, transport=транспорт)
        except Exception:  # noqa: BLE001
            упало = True
        check("стойкая перегрузка — честная ошибка после трёх попыток",
              упало and len(вызовы) == 3, str(вызовы))

        # Ошибка в самом запросе повтором не лечится — не тратим время гостя.
        транспорт, вызовы = _транспорт([400, 200])
        упало = False
        try:
            await _c._call_model({}, {}, transport=транспорт)
        except Exception:  # noqa: BLE001
            упало = True
        check("ошибка запроса (400) — без повторов", упало and вызовы == [400], str(вызовы))
    finally:
        _c.ПАУЗЫ_ПОВТОРА = было


async def qa_calls() -> None:
    """Звонок на номер бота.

    Green API не умеет ни принять звонок, ни сбросить — только сообщить о
    нём. Без реакции гость слушает гудки и решает, что отель не работает.
    Спросили 2026-10-04: «а когда звонки приходят, что делать?»
    """
    head("Звонки на номер бота")

    import inspect as _insp  # noqa: PLC0415
    import time as _t  # noqa: PLC0415

    import app.notify as _nt  # noqa: PLC0415
    import app.webhooks_api as _wh  # noqa: PLC0415
    from app.dialogs import load_history  # noqa: PLC0415

    отправлено: list[tuple[str, str]] = []
    отелю: list[str] = []

    class _Канал:
        def __init__(self, *_a, **_k) -> None:
            pass

        async def send(self, chat_id: str, text: str) -> str:
            отправлено.append((chat_id, text))
            return "ok"

    async def _факты(_settings, force: bool = False):  # noqa: ANN001
        return {"hotel": {"contacts": {"phonePrimary": "+7 (777) 531-00-09"}}}

    async def _отелю(text: str, что: str, *, corporate: bool = False) -> int:
        отелю.append(text)
        return 1

    from app.config import get_settings as _gs  # noqa: PLC0415

    settings = _gs()
    было = (_wh.WhatsAppChannel, _wh.load_facts, _nt._tell_hotel)
    _wh.WhatsAppChannel, _wh.load_facts, _nt._tell_hotel = _Канал, _факты, _отелю
    # Номер свой на каждый прогон: ответ — раз в день на гостя, и со
    # вчерашним номером второй прогон за день упёрся бы в эту защиту.
    гость = f"7701{int(_t.time()) % 10_000_000:07d}"
    звонок = lambda статус, кто=гость: {  # noqa: E731
        "typeWebhook": "incomingCall", "status": статус, "from": f"{кто}@c.us",
        "idMessage": f"CALL-{кто}-{статус}", "instanceData": {"wid": "77003002526@c.us"},
    }
    try:
        r = await _wh._звонок(settings, звонок("offer"))
        check("пока звонит — молчим: трубку могут взять", not отправлено and "skipped" in r, str(r))
        r = await _wh._звонок(settings, звонок("pickUp"))
        check("трубку взяли — не пишем", not отправлено and "skipped" in r, str(r))

        r = await _wh._звонок(settings, звонок("declined"))
        check("звонок не приняли — гостю написали", len(отправлено) == 1, str(r))
        текст = отправлено[0][1] if отправлено else ""
        check("написали в чат звонившего", bool(отправлено) and отправлено[0][0] == f"{гость}@c.us")
        check("в сообщении телефон стойки", "531-00-09" in текст, текст[:120])
        check("и по-английски — по звонку язык не узнать", "Hello" in текст)
        check("отелю сообщили о звонке", len(отелю) == 1, str(len(отелю)))
        check("в уведомлении номер гостя с одним плюсом",
              bool(отелю) and f"От: +{гость}" in отелю[0] and "++" not in отелю[0])
        # Читаем тем же подключением, каким пишет вебхук: раздел о схеме
        # перезагружает app.db, и свежий SessionLocal оттуда смотрит в другую
        # базу — проверка падала в общем прогоне и проходила в одиночку.
        история = await load_history(_wh.SessionLocal, _wh.WA_CHANNEL, f"{гость}@c.us")
        check("звонок записан в историю — на «я звонил» бот поймёт",
              any("звонок не принят" in str(m.get("content")) for m in история))

        r = await _wh._звонок(settings, звонок("hungUp"))
        check("второй звонок за день — без повторного сообщения",
              len(отправлено) == 1 and len(отелю) == 1 and r.get("duplicate"), str(r))

        r = await _wh._звонок(settings, звонок("declined", _wh.ПРОВЕРОЧНЫЙ_НОМЕР))
        check("проверочный номер отель не тревожит", len(отелю) == 1, str(r))

        r = await _wh._звонок(settings, {**звонок("declined"), "from": "120363000000@g.us"})
        check("групповой звонок пропускаем", "skipped" in r, str(r))
    finally:
        _wh.WhatsAppChannel, _wh.load_facts, _nt._tell_hotel = было

    check("вебхук отдаёт звонки сюда",
          "_звонок(settings, payload)" in _insp.getsource(_wh.whatsapp_webhook))


async def qa_airport() -> None:
    """Из аэропорта — и на языке гостя.

    Блок «Из аэропорта» на сайте делался для туристов, и бот обязан говорить
    то же самое: турист сверит одно с другим. Первый прогон 2026-09-30
    показал две беды. На английский вопрос бот отвечал по-русски — 2 из 2.
    И однажды сам придумал пересадку «у метро Байконур»: в справке были
    номера автобусов, но не путь, и модель его дорисовала. Турист пошёл бы
    искать место, которого в маршруте нет.
    """
    head("Из аэропорта и язык гостя")

    from app.concierge import _language_note, _with_note  # noqa: PLC0415
    from app.knowledge import _airport_path  # noqa: PLC0415

    шаги_96 = [{"kind": "walk", "minutes": 6}, {"kind": "bus", "lines": ["96"]},
               {"kind": "trolley", "lines": ["7", "30"]}, {"kind": "walk", "minutes": 7}]
    путь = _airport_path(шаги_96)
    check("путь собирается по шагам",
          путь == "пешком 6 мин → автобус 96 → троллейбус 7 или 30 → пешком 7 мин", путь)
    check("мусор в шагах не роняет бриф", _airport_path([None, "x", {"kind": "?"}]) == "")

    факты = {
        "hotel": {}, "policy": {}, "rooms": [],
        "airport": {
            "distance": "17 км", "checked": "2026-09-29",
            "options": [{"title": "Автобус 96 + троллейбус 7 или 30", "time": "около 1,5 часа",
                         "price": "240 ₸", "note": "", "steps": шаги_96},
                        {"title": "Такси", "time": "около 30 минут", "price": "около 3 700 ₸",
                         "note": "", "steps": []}],
            "payment": "Проезд — 120 ₸ по карте Onay.",
            "routeGoogle": "https://www.google.com/maps/dir/?api=1&travelmode=transit",
        },
    }
    бриф = render_brief(факты)
    check("в брифе есть блок про аэропорт", "КАК ДОБРАТЬСЯ ИЗ АЭРОПОРТА" in бриф)
    check("путь автобуса дан по шагам", f"Путь: {путь}." in бриф)
    check("у такси пути нет — и строки пустой нет", бриф.count("Путь:") == 1)
    check("ссылка на живой маршрут в брифе", "travelmode=transit" in бриф)
    check("запрещено называть остановки самому", "не называй их" in бриф)
    check("автобус 92 отсечён", "92" in бриф and "не советуй" in бриф)
    check("без аэропорта в справке бриф не падает и блока нет",
          "АЭРОПОРТА" not in render_brief({"hotel": {}, "policy": {}}))

    # Язык. Пометка идёт в саму реплику гостя: правило в своде проиграло
    # длинному русскому брифу.
    check("английский — пометка", "НЕ по-русски" in _language_note("how can I get from the airport?"))
    check("в пометке названо приветствие «Hello»",
          "Hello" in _language_note("Hi! What's the cheapest way?"))
    check("казахский — пометка по-казахски",
          "по-казахски" in _language_note("Әуежайдан қалай жетуге болады?"))
    check("русский — без пометки", _language_note("как добраться из аэропорта?") == "")
    # Приветствие — только в первом ответе. Пометка требовала его всегда, и на
    # казахском бот начинал «Сәлеметсіз бе!» каждый ответ (2026-10-05).
    check("в середине разговора — без нового приветствия",
          "Сәлеметсіз" not in _language_note("Жақсы, аламын", first=False)
          and "Hello" not in _language_note("Great, thanks", first=False))
    check("в первом ответе приветствие названо",
          "Сәлеметсіз" in _language_note("Сәлем", first=True))
    # Русский гость пишет латиницей названия — это не повод переходить на
    # английский.
    check("русский с латиницей — без пометки", _language_note("Comfort Plus на 20-е") == "")
    check("одни цифры — без пометки", _language_note("12-13") == "")

    сообщения = [{"role": "user", "content": "how much?"}]
    с_пометкой = _with_note(сообщения, 0, _language_note("how much?"))
    check("пометка доходит до модели", "НЕ по-русски" in str(с_пометкой[0]["content"]))
    check("а в историю уходит чистый текст", сообщения[0]["content"] == "how much?")


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
    # Блок «Из аэропорта» на сайте и ответ бота — из одного источника.
    аэропорт = facts.get("airport") or {}
    автобусы = [o for o in аэропорт.get("options", []) if o.get("steps")]
    check("справка отдаёт маршруты из аэропорта с шагами", len(автобусы) >= 2, str(len(автобусы)))
    check("и они попадают в бриф", "КАК ДОБРАТЬСЯ ИЗ АЭРОПОРТА" in brief and "Путь:" in brief)
    # Оценка гостей — та же, что в блоке на главной.
    отзывы = facts.get("reviews") or {}
    check("справка отдаёт оценку гостей", bool(отзывы.get("rating")), str(отзывы)[:80])
    check("и она попадает в бриф", "ОТЗЫВЫ:" in brief)
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
    # Наружу этот набор писать не должен НИЧЕГО.
    #
    # Он ходит по настоящим ключам из backend/.env — так и задумано, иначе
    # не проверить ни Exely, ни модель. Но у отправки сообщений цена другая:
    # проверка, которая пишет живому человеку, — это уже не проверка.
    #
    # Так уже случалось дважды. Первый раз набор разослал 18 сообщений в
    # WhatsApp. Второй — когда уведомление о корпоративной заявке переехало
    # из незаведённого Telegram в работающий WhatsApp: раздел про заявки
    # молча начал слать их по-настоящему. Поэтому глушим не по одному
    # месту, а целиком и в самом начале.
    import app.notify as _notify  # noqa: PLC0415

    отправлено_наружу: list[tuple[str, str]] = []

    async def _вместо_отправки(text: str, что: str, *, corporate: bool = False) -> int:
        отправлено_наружу.append((что, text))
        return 1

    # Настоящую отправку сохраняем: раздел о ресепшене проверяет, КОМУ она
    # пишет, и с подменой проверял бы саму подмену. Канал WhatsApp он при
    # этом подменяет сам — наружу ничего не уходит.
    _notify._tell_hotel_настоящий = _notify._tell_hotel
    _notify._tell_hotel = _вместо_отправки

    # Разработчику — тоже никуда: канал завёлся 2026-10-05 и шлёт в WhatsApp
    # и Telegram напрямую, мимо _tell_hotel.
    async def _вместо_разработчику(text: str, что: str) -> int:
        отправлено_наружу.append((что, text))
        return 1

    _notify.tell_developer_настоящий = _notify.tell_developer
    _notify.tell_developer = _вместо_разработчику

    qa_time()
    qa_exely_parsing()
    qa_modes()
    await qa_tools()
    await qa_exely_api()
    await qa_booking_sync()
    qa_webhooks()
    qa_freedompay()
    qa_payments()
    await qa_hybrid()
    await qa_access()
    await qa_channels()
    await qa_corporate()
    await qa_followup()
    await qa_funnel()
    await qa_refunds()
    await qa_payment_callback()
    await qa_unpaid()
    await qa_schema()
    await qa_corp_pending()
    await qa_memory_week()
    await qa_reception_notify()
    await qa_annotations()
    await qa_undelivered()
    await qa_model_retry()
    await qa_front_desk()
    await qa_daily_check()
    await qa_credits_alert()
    await qa_numeric_history()
    await qa_guest_language_everywhere()
    await qa_staff_images_facts()
    await qa_price_sync()
    await qa_site_reviews()
    await qa_nearest_and_style()
    await qa_followup_own()
    await qa_guest_messages_language()
    await qa_chat_turn()
    await qa_empty_answer()
    await qa_calls()
    await qa_airport()
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
