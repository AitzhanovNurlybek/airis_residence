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

    # Инструкцию себе консьерж читает на «ты» и переносил это на гостя.
    # Замерено 2026-08-30 на двенадцати ответах: каждый четвёртый уходил с
    # «пришли номер брони» и «назови фамилию». Для отеля это заметно сразу.
    check("к гостю обращаются на «вы»", "Гостю — всегда на «вы»" in live_mode)

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
          "какие даты выбрать в форме" in live_mode)
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
          "текстом" in UNREADABLE.lower())
    check("текст ответа говорит, чем можно помочь",
          "свободные номера" in UNREADABLE)

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
    # Пустые поля не должны превращаться в «None»: заявку читает человек.
    bare = "\n".join(lead_lines(_Lead(id=8, name="Аноним", phone="+77010000001")))
    check("пустые поля заявки не показываются как None", "None" not in bare, bare[:80])
    check("незаполненная категория названа словами", "не выбран" in bare)

    # Получателей уведомлений может быть несколько: владелец и менеджер на
    # смене. Добавлять второго правкой кода неправильно, поэтому список.
    from app.config import Settings as _S  # noqa: PLC0415

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

    оплачен = {"pg_payment_id": "1841766142", "pg_amount": "50000",
               "pg_card_pan": "555555******4444"}

    def бронь(**поля):
        основа = {
            "number": "20260917-509506-1262598144",
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
    check("платёж подхвачен", plan.payment_id == "1841766142")
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

    # Без ключей банка отправлять некуда, но и падать нельзя.
    done, note = await execute(_S(refund_auto=True, refund_max=0), готовый)
    check("без доступа к банку возврат не уходит", not done, note)
    check("причина понятна", "не настроен" in note, note)

    # ── Что видит отель ────────────────────────────────────────────────
    текст = "\n".join(describe(готовый, False, "автоматический возврат выключен"))
    for нужно in ("20260917-509506-1262598144", "50000", "1841766142"):
        check(f"в сообщении есть «{нужно}»", нужно in текст)
    check("сказано, что делать руками", "кабинете FreedomPay" in текст)

    сделан = "\n".join(describe(готовый, True, "принят банком"))
    check("выполненный возврат назван выполненным", "Возврат отправлен" in сделан)
    check("гостю обещан честный срок", "1–7 рабочих дней" in сделан)

    пусто = "\n".join(describe(полностью, False, полностью.problem))
    check("когда возвращать нечего, заголовок не обещает возврат",
          "не требуется" in пусто, пусто[:60])


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
    await qa_corporate()
    await qa_followup()
    await qa_funnel()
    await qa_refunds()
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
