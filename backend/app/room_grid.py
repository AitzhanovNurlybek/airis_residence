"""
Шахматка отеля из Exely: сколько номеров каждой категории свободно на самом деле.

Зачем. Наличие бот узнаёт у формы бронирования — то же, что видит гость на
сайте. Это правда о том, что продаётся онлайн, но не о том, что свободно в
отеле: часть номеров отель держит в резерве, тариф бывает закрыт на даты,
снятую бронь убирают не сразу. Гость слышал «мест нет» и уходил, хотя на
стойке номер бы нашли. Отель попросил (2026-11-23), чтобы бот в таком случае
«пробивал через шахматку».

Откуда. PMS API Exely — тот же договорной доступ, что у поиска броней:
номера отеля (`rooms`), брони на даты (`reservations/search`) и у каждой
брони проживания с категорией, назначенным номером и датами
(`reservations/{номер}`). Готового остатка по категориям API не отдаёт,
поэтому считаем сами: номер занят в ночь, если на него назначено проживание
(новое или уже заселённое); проживание без назначенного номера занимает один
номер своей категории. Проверено на живых данных 2026-11-23: 34 номера,
40 броней на три ночи.

Чего здесь не видно. Номера на ремонте в этих данных не отмечены, поэтому
шахматка — подсказка, а не обещание: подтверждает стойка.

Медленно. Деталь каждой брони — отдельный запрос (~1 с), на три ночи это
около сорока броней. Поэтому шахматку смотрим только тогда, когда онлайн не
продаётся ничего, читаем параллельно и в пределах бюджета времени, а
прочитанное держим в памяти несколько минут. Не уложились — None, и бот
отвечает как раньше: неполная шахматка показала бы свободным занятое.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import date, timedelta
from typing import Any

from .booking_system.exely import ROOM_TYPES

logger = logging.getLogger(__name__)

#: Номера отеля меняются редко — список держим полдня.
ROOMS_TTL = 6 * 3600
#: Деталь брони — десять минут: за это время её могут изменить, но бот
#: спрашивает о тех же датах обычно несколько раз подряд.
DETAIL_TTL = 600
#: Одновременных запросов. Лимит Exely — десять в секунду, деталь идёт ~1 с.
PARALLEL = 6
#: Секунд на всю шахматку. Гость ждёт ответа в мессенджере. Замер 2026-11-23:
#: первое чтение (токен, номера, 40 броней) — 10,3 с, новые даты потом ~5 с,
#: повтор из памяти — меньше секунды.
BUDGET = 15.0
#: Страниц поиска броней по сто штук. Отелю на 34 номера хватает одной.
MAX_PAGES = 5
#: Длиннее — разговор со стойкой о долгом проживании, а не проверка ботом.
MAX_NIGHTS = 14

#: Проживание занимает номер, пока гость не выехал.
ЗАНИМАЕТ = {"New", "CheckedIn"}
#: Брони, которые номер не держат.
СНЯТЫЕ = {"Cancelled", "Released"}

_api: dict[str, Any] = {"api": None, "key": ""}
_rooms: dict[str, Any] = {"at": 0.0, "rooms": []}
_details: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _client(settings: Any) -> Any:
    """Один клиент на процесс: токен Exely живёт 15 минут, а выдают его не чаще 15 раз в минуту."""
    ключ = f"{settings.exely_property_id}|{settings.exely_api_base}|{settings.exely_auth_url}"
    if _api["api"] is None or _api["key"] != ключ:
        from .booking_system.exely_api import ExelyApi  # noqa: PLC0415

        _api["api"] = ExelyApi(
            settings.exely_client_id, settings.exely_client_secret, settings.exely_property_id,
            auth_url=settings.exely_auth_url, api_base=settings.exely_api_base, timeout=10.0)
        _api["key"] = ключ
    return _api["api"]


async def _all_rooms(api: Any, property_id: str) -> list[tuple[str, str]]:
    """Номера отеля: (идентификатор номера, код категории)."""
    if _rooms["rooms"] and time.monotonic() - _rooms["at"] < ROOMS_TTL:
        return _rooms["rooms"]
    rooms: list[tuple[str, str]] = []
    params: dict[str, Any] = {"maxPageSize": 100}
    for _ in range(MAX_PAGES):
        data = await api._get(f"/properties/{property_id}/rooms", params, base=api.pms_base)
        data = data if isinstance(data, dict) else {}
        for room in data.get("rooms") or []:
            if isinstance(room, dict) and room.get("id"):
                rooms.append((str(room["id"]), str(room.get("roomTypeId") or "")))
        if not data.get("hasNextPage") or not data.get("nextPageToken"):
            break
        params = {"maxPageSize": 100, "pageToken": data["nextPageToken"]}
    if rooms:
        _rooms["rooms"], _rooms["at"] = rooms, time.monotonic()
    return rooms


async def _numbers(api: Any, property_id: str, check_in: date, check_out: date) -> list[str]:
    """Номера действующих броней, задевающих эти ночи."""
    # Окно — от дня заезда после обеда до утра выезда: брони, выезжающие
    # утром в день заезда или заезжающие в день выезда, ночей не делят.
    params: dict[str, Any] = {
        "startAffectPeriodDateTime": f"{check_in.isoformat()}T13:00",
        "endAffectPeriodDateTime": f"{check_out.isoformat()}T11:00",
        "state": "Active",
        "maxPageSize": 100,
    }
    out: list[str] = []
    for _ in range(MAX_PAGES):
        data = await api._get(f"/properties/{property_id}/reservations/search", params,
                              base=api.pms_base)
        data = data if isinstance(data, dict) else {}
        out += [str(r["number"]) for r in data.get("reservations") or []
                if isinstance(r, dict) and r.get("number")]
        if not data.get("hasNextPage") or not data.get("nextPageToken"):
            break
        params = {**params, "pageToken": data["nextPageToken"]}
    return list(dict.fromkeys(out))


async def _stays(api: Any, property_id: str, number: str) -> list[dict[str, Any]]:
    """Проживания одной брони, которые держат номер."""
    было = _details.get(number)
    if было and time.monotonic() - было[0] < DETAIL_TTL:
        return было[1]
    data = await api._get(f"/properties/{property_id}/reservations/{number}",
                          {"languageCode": "en"}, base=api.pms_base, missing_on_400=True)
    бронь = (data or {}).get("reservation") if isinstance(data, dict) else None
    stays: list[dict[str, Any]] = []
    if isinstance(бронь, dict) and бронь.get("reservationStatus") not in СНЯТЫЕ:
        for st in бронь.get("roomStays") or []:
            if not isinstance(st, dict) or st.get("status") not in ЗАНИМАЕТ:
                continue
            заезд, выезд = _day(st.get("checkInDateTime")), _day(st.get("checkOutDateTime"))
            if заезд and выезд and выезд > заезд:
                stays.append({"room": str(st.get("roomId") or ""),
                              "type": str(st.get("roomTypeId") or ""),
                              "in": заезд, "out": выезд})
    if len(_details) > 500:
        граница = time.monotonic() - DETAIL_TTL
        for ключ in [k for k, (t, _) in _details.items() if t < граница]:
            _details.pop(ключ, None)
    _details[number] = (time.monotonic(), stays)
    return stays


def count_free(rooms: list[tuple[str, str]], stays: list[dict[str, Any]],
               check_in: date, check_out: date) -> dict[str, int]:
    """Сколько номеров каждой категории свободно во ВСЕ ночи: код категории → число.

    Номер с назначенным проживанием занят, в какой бы категории ни было
    продано проживание (переселение и апгрейд занимают тот номер, где живёт
    гость). Проживание без номера забирает один номер своей категории.
    """
    категория = dict(rooms)
    всего = Counter(t for _, t in rooms)
    меньше_всего: dict[str, int] = {}
    ночь = check_in
    while ночь < check_out:
        заняты: set[str] = set()
        без_номера: Counter[str] = Counter()
        for st in stays:
            if not st["in"] <= ночь < st["out"]:
                continue
            if st["room"] in категория:
                заняты.add(st["room"])
            else:
                без_номера[st["type"]] += 1
        for тип in всего:
            свободны = sum(1 for номер, t in rooms if t == тип and номер not in заняты)
            свободно = max(0, свободны - без_номера.get(тип, 0))
            меньше_всего[тип] = min(меньше_всего.get(тип, свободно), свободно)
        ночь += timedelta(days=1)
    return меньше_всего


async def free_by_category(settings: Any, check_in: date, check_out: date) -> dict[str, int] | None:
    """Свободно на все ночи по шахматке: код категории сайта → номеров. None — не узнали."""
    ночей = (check_out - check_in).days
    if not getattr(settings, "exely_api_ready", False) or not 0 < ночей <= MAX_NIGHTS:
        return None
    api = _client(settings)
    pid = str(settings.exely_property_id)

    async def _read() -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
        # Токен — до параллельных запросов: иначе каждый попросит свой, а
        # Exely выдаёт не больше трёх в секунду и пятнадцати в минуту.
        await api.token()
        rooms = await _all_rooms(api, pid)
        numbers = await _numbers(api, pid, check_in, check_out)
        очередь = asyncio.Semaphore(PARALLEL)

        async def одна(number: str) -> list[dict[str, Any]]:
            async with очередь:
                return await _stays(api, pid, number)

        группы = await asyncio.gather(*(одна(n) for n in numbers))
        return rooms, [st for группа in группы for st in группа]

    начало = time.monotonic()
    try:
        rooms, stays = await asyncio.wait_for(_read(), BUDGET)
    except Exception as error:  # noqa: BLE001 — без шахматки бот отвечает как раньше
        logger.warning("Шахматка Exely не прочиталась за %.1f с: %s",
                       time.monotonic() - начало, type(error).__name__)
        return None
    if not rooms:
        return None
    logger.info("Шахматка Exely %s—%s: проживаний %d, %.1f с", check_in, check_out,
                len(stays), time.monotonic() - начало)
    свободно = count_free(rooms, stays, check_in, check_out)
    return {ROOM_TYPES[код]: n for код, n in свободно.items() if код in ROOM_TYPES}
