"""
Ближайшие свободные даты, когда на запрошенные мест нет.

Зачем. 2026-10-07 гость писал по-казахски про 14–17 октября. Мест на все три
ночи не было — бот сказал правду, но дальше три раза переспросил гостя
(«какой месяц», «какие даты посмотреть», «сами позвоните или посмотреть?»),
хотя 17–20 октября свободно сразу в трёх категориях. Гость написал «позвоню»
и ушёл. Отель почти полный, и каждый такой уход — потерянная бронь.

Что делаем. Когда на даты гостя нет ничего, сами смотрим, что свободно рядом:
по ночам, потом проверяем найденное настоящим запросом на весь период. Бот
получает готовые варианты («17–20 октября, Comfort Plus от 47 250») и
называет один-два, а не отправляет гостя звонить.

Не выдумываем. Каждый вариант подтверждён тем же запросом наличия, которым
гость потом откроет форму брони.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

#: На сколько дней назад от даты заезда смотреть. Раньше заезжать гостю обычно
#: не хочется, но «на день раньше» бывает удобнее, чем «на неделю позже».
BACK_DAYS = 3

#: И на сколько дней вперёд. Неделя — потолок: дальше это уже другая поездка.
FORWARD_DAYS = 8

#: Сколько запросов наличия идёт одновременно. Exely держит десятки в секунду,
#: а нам важна скорость ответа гостю: 12 ночей за три-четыре секунды.
PARALLEL = 6

#: Потолок на весь поиск. Дольше гость уже не ждёт ответа в мессенджере, и
#: без вариантов бот отвечает как раньше — «свободных не видно».
TIME_LIMIT = 14.0

#: Сколько вариантов отдаём боту. Два: ближайший и запасной. Больше гость не
#: прочитает, а бот назовёт всё равно один.
MAX_OPTIONS = 2


@dataclass
class Option:
    """Свободное окно: даты, сколько ночей и что в нём свободно."""

    check_in: date
    check_out: date
    nights: int
    #: slug → (название, цена за ночь в самом дешёвом тарифе или None)
    rooms: dict[str, tuple[str, int | None]] = field(default_factory=dict)

    @property
    def cheapest(self) -> int | None:
        цены = [p for _, p in self.rooms.values() if p]
        return min(цены) if цены else None


def _cheapest_rate(offer: Any) -> int | None:
    """Самая низкая цена за ночь среди тарифов предложения."""
    цены = []
    for rate in getattr(offer, "rates", ()) or ():
        price = getattr(rate, "price", None)
        if price:
            цены.append(int(price))
    if цены:
        return min(цены)
    price = getattr(offer, "price_per_night", None)
    return int(price) if price else None


async def _free_by_night(booking: Any, first: date, last: date, guests: int) -> dict[date, set[str]]:
    """Какие категории свободны в каждую ночь от `first` до `last` включительно."""
    gate = asyncio.Semaphore(PARALLEL)
    out: dict[date, set[str]] = {}

    async def one(day: date) -> None:
        async with gate:
            try:
                result = await booking.availability(day, day + timedelta(days=1), guests=guests)
            except Exception as error:  # noqa: BLE001 — одна ночь не повод бросать поиск
                logger.warning("Наличие на ночь %s не получено: %s", day, error)
                return
            out[day] = {o.room_slug for o in result.offers if o.rooms_left}

    days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    await asyncio.gather(*(one(d) for d in days))
    return out


def _candidates(nights: dict[date, set[str]], check_in: date, check_out: date,
                today: date) -> list[tuple[date, int]]:
    """Окна (заезд, ночей), где хотя бы одна категория свободна все ночи.

    Сначала окна той же длины, что хотел гость; если их нет — на ночь-две
    короче. Ближе к желаемой дате — раньше в списке.
    """
    хотел = (check_out - check_in).days
    found: list[tuple[int, int, date, int]] = []
    for длина in range(хотел, max(1, хотел - 3), -1):
        for shift in range(-BACK_DAYS, FORWARD_DAYS + 1):
            start = check_in + timedelta(days=shift)
            if start < today:
                continue
            ночи = [start + timedelta(days=n) for n in range(длина)]
            if any(d not in nights for d in ночи):
                continue
            общие = set.intersection(*(nights[d] for d in ночи))
            if not общие:
                continue
            if длина < хотел and not (start <= check_out and start + timedelta(days=длина) >= check_in):
                continue  # укороченное окно имеет смысл, только если пересекает желаемое
            found.append((хотел - длина, abs(shift), start, длина))
        if found:
            break  # нашли окна этой длины — короче не нужно
    found.sort(key=lambda x: (x[0], x[1], x[2]))
    out: list[tuple[date, int]] = []
    seen: set[date] = set()
    for _, _, start, длина in found:
        if start in seen:
            continue
        seen.add(start)
        out.append((start, длина))
    return out


async def nearest_options(booking: Any, check_in: date, check_out: date, guests: int,
                          today: date) -> list[Option]:
    """Свободные окна рядом с датами гостя, подтверждённые настоящим запросом."""
    хотел = (check_out - check_in).days
    first = max(today, check_in - timedelta(days=BACK_DAYS))
    last = check_in + timedelta(days=FORWARD_DAYS + хотел)
    try:
        nights = await asyncio.wait_for(_free_by_night(booking, first, last, guests), TIME_LIMIT)
    except asyncio.TimeoutError:
        logger.warning("Поиск ближайших дат не уложился в %s с", TIME_LIMIT)
        return []

    options: list[Option] = []
    for start, длина in _candidates(nights, check_in, check_out, today):
        # Окна, начинающиеся день за днём, почти одинаковы («17–20», «18–21»,
        # «19–22»): гостю нужен выбор, а не три копии одного и того же.
        if any(abs((start - o.check_in).days) < 2 for o in options):
            continue
        end = start + timedelta(days=длина)
        try:
            result = await booking.availability(start, end, guests=guests)
        except Exception as error:  # noqa: BLE001
            logger.warning("Проверка окна %s—%s не удалась: %s", start, end, error)
            continue
        rooms = {o.room_slug: (o.room_name or o.room_slug, _cheapest_rate(o))
                 for o in result.offers if o.rooms_left}
        if rooms:
            options.append(Option(start, end, длина, rooms))
        if len(options) >= MAX_OPTIONS:
            break
    return options
