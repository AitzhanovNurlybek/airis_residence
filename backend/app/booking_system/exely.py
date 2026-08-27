"""
Exely: чтение наличия работает уже сейчас, запись — нет.

Долгое время считалось, что до ответа интеграторов от Exely нам недоступно
ничего. Это оказалось неверно, и выяснилось простым вопросом владельца: если
доступа нет, откуда на сайте работает форма поиска номеров?

Форма — это виджет Exely, встроенный в страницу их же скриптом. Сам по себе он
нам ничего не даёт: это чужой интерфейс внутри нашей страницы. Но чтобы
показать гостю свободные номера, он ходит за ними на открытый адрес, и туда
может сходить и наш сервер. Ровно те же данные, что видит гость, — не больше.

ЧТО ЭТО ЗНАЧИТ НА ПРАКТИКЕ

Читать наличие и цены — можно, и это настоящие числа из шахматки отеля, а не
выдуманные. Консьерж перестаёт говорить «наличие подтвердит стойка» и начинает
отвечать по делу.

Создавать, менять и отменять брони — нельзя. Здесь этих методов просто нет, и
это не забывчивость: оформление брони затрагивает деньги и обязательства
отеля, такое делают через договорной интерфейс с ключом и поддержкой, а не
через адрес, подсмотренный у виджета.

ЧЕГО ЖДАТЬ ОТ ЭТОГО РЕШЕНИЯ

Адрес недокументированный. Он может измениться в любой день без предупреждения
— поставщик ничего нам не обещал. Поэтому любая ошибка здесь не роняет ответ
гостю: система честно говорит, что свериться не вышла, и зовёт стойку.
Официальный доступ у интеграторов всё равно нужно просить: он даст запись,
уведомления об изменениях и обязательство поддерживать формат.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from urllib.parse import urlencode

import httpx

from .base import Availability, BookingSystemUnavailable, RatePlan, RoomOffer

logger = logging.getLogger(__name__)

#: Параметры интеграции, выданные отелю. Те же, что в виджете на сайте.
HOTEL_CODE = "509506"
WIDGET_CONTEXT = "BE-INT-airisresidence_2026-08-13"
IBE_HOST = "https://kz-ibe.hopenapi.com"

#: Коды категорий в Exely. Те же числа лежат в `beRoomType` в site.ts —
#: по ним форма брони открывается сразу на нужном номере.
#:
#: Apart отеля здесь есть, а на сайте такой категории нет вовсе. Оставлен
#: намеренно: пусть наличие по нему видно, даже пока страницы нет.
ROOM_TYPES: dict[str, str] = {
    "5054709": "standart-single",
    "5050493": "standart",
    "5050494": "standart-twin",
    "5050496": "comfort",
    "5050495": "comfort-plus",
    "5070642": "apart",
}

#: Тарифы отеля. Название говорит о завтраке прямо, но полагаться на текст
#: одного поля нельзя: переименуют — и мы начнём обещать завтрак там, где его
#: нет. Поэтому знание закреплено кодом, а разбор названия остаётся запасным.
RATE_PLANS: dict[str, tuple[str, bool]] = {
    "10123672": ("Выгодные выходные", True),
    "10139493": ("Тариф без завтрака", False),
    "10145264": ("Best Deal: с завтраком", True),
}

# Обратная сторона ROOM_TYPES: по slug сайта — код категории в Exely.
# Строится из того же словаря, чтобы код категории нельзя было завести
# в двух местах и разойтись.
CODES: dict[str, str] = {slug: code for code, slug in ROOM_TYPES.items()}


def booking_form_url(
    site_url: str,
    *,
    room_slug: str = "",
    check_in: date | str | None = None,
    check_out: date | str | None = None,
    guests: int = 0,
) -> str:
    """Ссылка на страницу /booking с подставленными датами и категорией.

    Бронь через API Exely создать нельзя — такого метода нет вовсе (см.
    docs/EXELY_API.md). Единственный способ довести гостя до брони — форма
    Exely на нашей же странице. Консьерж присылает ссылку, гость подтверждает
    сам.

    Про параметры. `room-type` форма читает — на нём построены кнопки
    «Забронировать» на страницах номеров. Даты и число гостей передаются
    именами, которые использует сайт; подхватывает ли их виджет, до конца
    не проверено. Если не подхватит, гость просто выберет даты в самой форме:
    ссылка всё равно открывает нужную страницу, а не ведёт в никуда.
    """
    params: list[tuple[str, str]] = []
    code = CODES.get(room_slug, "")
    if code:
        params.append(("room-type", code))
    if check_in:
        params.append(("checkin", str(check_in)))
    if check_out:
        params.append(("checkout", str(check_out)))
    if guests > 0:
        params.append(("adults", str(guests)))

    base = site_url.rstrip("/") + "/booking"
    return f"{base}?{urlencode(params)}" if params else base


NAMES: dict[str, str] = {
    "standart-single": "Standart Single",
    "standart": "Standart",
    "standart-twin": "Standart Twin",
    "comfort": "Comfort",
    "comfort-plus": "Comfort Plus",
    "apart": "Apart",
}

WRITE_NOT_READY = (
    "Оформление брони через Exely не подключено: нужен договорной доступ к API. "
    "Пока заявку подтверждает менеджер отеля."
)


class ExelyBookingSystem:
    """Настоящее наличие из Exely. Только чтение."""

    name = "Exely (наличие)"
    source = "exely"

    def __init__(
        self,
        hotel_code: str = HOTEL_CODE,
        host: str = IBE_HOST,
        room_names: dict[str, str] | None = None,
        timeout: float = 12.0,
    ) -> None:
        # Код отеля уходит в query-строку чужого сервиса, и проверить его
        # там некому: на неверный код Exely отвечает 200 с пустым результатом.
        # Пустой результат неотличим от «всё занято» — консьерж начнёт всем
        # отказывать, и никто не заметит, потому что ошибки нет. Опечатка в
        # переменной окружения обязана падать здесь и сразу.
        code = str(hotel_code).strip()
        if not code.isdigit():
            raise ValueError(
                f"Код отеля Exely должен быть числом, получено {code[:40]!r}. "
                "Проверь EXELY_HOTEL_CODE."
            )
        self._hotel = code
        self._host = host.rstrip("/")
        self._names = room_names or {}
        self._timeout = timeout

    def display(self, slug: str) -> str:
        return self._names.get(slug) or NAMES.get(slug, slug)

    async def availability(self, check_in: date, check_out: date) -> Availability:
        nights = (check_out - check_in).days
        if nights <= 0:
            return Availability(check_in, check_out, 0, [], "exely")

        query = {
            "include_all_placements": "false",
            "include_promo_restricted": "true",
            "include_rates": "true",
            "include_transfers": "false",
            "language": "ru-ru",
            # Двое взрослых — потому что нас интересует, свободен ли номер, а
            # не сколько он стоит одному. Цену мы всё равно берём из своего
            # прайса: он совпадает с Exely и не зависит от акций, которые
            # сегодня есть, а завтра нет.
            "criterions[0].adults": "2",
            "criterions[0].dates": f"{check_in.isoformat()};{check_out.isoformat()}",
            "criterions[0].hotels[0].code": self._hotel,
        }
        url = f"{self._host}/ApiWebDistribution/BookingForm/hotel_availability?{urlencode(query)}"
        headers = {
            "Accept": "application/json",
            # Запрос от имени сайта отеля: это тот же адрес, который открывает
            # виджет на наших же страницах.
            "Referer": "https://airisresidence.kz/",
            "Origin": "https://airisresidence.kz",
            "User-Agent": "AirisResidence/1.0 (+https://airisresidence.kz)",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as error:  # noqa: BLE001
            logger.warning("Exely не ответил про наличие: %s", error)
            raise BookingSystemUnavailable(f"Exely не ответил: {error}") from error

        return Availability(check_in, check_out, nights, self._offers(data, nights), "exely")

    def _offers(self, data: dict[str, Any], nights: int = 1) -> list[RoomOffer]:
        """
        Свободные номера из ответа Exely.

        Ответ устроен как список вариантов размещения (`room_stays`), а не как
        список категорий: одна и та же категория приходит несколько раз с
        разными тарифами. Нас интересует худший случай по каждой категории —
        сколько номеров осталось, а не по какому тарифу их продают.
        """
        # Точные остатки лежат отдельным списком: у каждой квоты свой rph и
        # количество. В самих вариантах размещения есть limited_inventory_count,
        # но он приходит не всегда — только когда номеров осталось мало.
        quotas = {
            str(q.get("rph")): int(q.get("quantity") or 0)
            for q in data.get("room_type_quotas") or []
        }

        left: dict[str, int] = {}
        rates: dict[str, dict[str, RatePlan]] = {}

        for stay in data.get("room_stays") or []:
            plans = stay.get("rate_plans") or []
            for room_type in stay.get("room_types") or []:
                code = str(room_type.get("code") or "")
                slug = ROOM_TYPES.get(code)
                if not slug:
                    # Новая категория, о которой мы не знаем. Пропускаем молча:
                    # выдумывать для неё название и показывать гостю нельзя.
                    logger.info("Exely прислал незнакомую категорию %s", code)
                    continue

                count = quotas.get(str(room_type.get("room_type_quota_rph")))
                if count is None:
                    count = room_type.get("limited_inventory_count")
                if count is None:
                    # Ни квоты, ни признака дефицита: номер продаётся, а
                    # сколько их — неизвестно. Считать это нулём нельзя, иначе
                    # откажем гостю в свободном номере.
                    count = max(left.get(slug, 0), 1)
                left[slug] = max(left.get(slug, 0), int(count))

                for plan in plans:
                    parsed = _rate(plan, room_type, nights)
                    if parsed is not None:
                        rates.setdefault(slug, {})[parsed.code] = parsed

        # Категории, которых в ответе не оказалось вовсе, свободными не
        # считаются: Exely присылает только то, что продаётся на эти даты.
        for slug in ROOM_TYPES.values():
            left.setdefault(slug, 0)

        offers = []
        for slug, count in sorted(left.items()):
            plans = tuple(sorted(rates.get(slug, {}).values(), key=lambda r: r.price))
            offers.append(
                RoomOffer(
                    room_slug=slug,
                    room_name=self.display(slug),
                    rooms_left=count,
                    # Цена — самая низкая из доступных сегодня. Именно её гость
                    # увидит в форме брони, и именно её должен называть
                    # консьерж: прайс на сайте выше продажной цены.
                    price_per_night=plans[0].price if plans else None,
                    source="exely",
                    rates=plans,
                )
            )
        return offers

    # ─── Запись: сознательно не реализована ───

    async def get_booking(self, external_id: str):
        raise BookingSystemUnavailable(WRITE_NOT_READY)

    async def invoices(self, *, company_bin: str = "", external_id: str = ""):
        raise BookingSystemUnavailable(WRITE_NOT_READY)


def _rate(plan: dict[str, Any], room_type: dict[str, Any], nights: int = 1) -> RatePlan | None:
    """Тариф с ценой за ночь для конкретной категории.

    Exely присылает цену за весь период проживания, а не за ночь: на две ночи
    в Comfort приходит 81 000 при цене 40 500 за ночь. Мы кладём в RatePlan
    цену за ночь, потому что именно её называет консьерж и именно её показывает
    сайт. Без деления консьерж говорил гостю двойную цену на двух ночах и
    тройную на трёх — и звучало это правдоподобно, поэтому не бросалось в глаза.
    """
    code = str(plan.get("code") or "")
    known = RATE_PLANS.get(code)
    if known:
        name, breakfast = known
    else:
        name = str(plan.get("name") or f"тариф {code}").strip()
        low = name.casefold()
        # Запасной разбор для тарифов, которых мы ещё не видели. «Не знаю»
        # честнее выдумки: пусть консьерж промолчит про завтрак, чем пообещает.
        breakfast = False if "без завтрак" in low else (True if "завтрак" in low else None)

    placements = room_type.get("placements") or []
    if not placements:
        return None
    first = placements[0]
    price = first.get("price_after_tax")
    if price is None:
        return None

    discount = first.get("discount") or {}
    was = discount.get("basic_after_tax")

    per_night = max(int(nights), 1)
    price_night = int(round(float(price) / per_night))
    was_night = int(round(float(was) / per_night)) if was else 0

    return RatePlan(
        cancellation=_cancellation(plan),
        code=code,
        name=name,
        price=price_night,
        breakfast=breakfast,
        was=was_night if was_night and was_night != price_night else None,
    )


def _cancellation(plan: dict[str, Any]) -> str:
    """
    Условия отмены словами отеля.

    Берём их у Exely, а не пишем сами. Условия у каждого тарифа свои, отель
    меняет их в своём кабинете, и наша копия отстанет молча. А сказанное
    гостю про отмену — это то, на что он будет ссылаться при споре.

    Из группы берём формулировку со сроком, если она есть: «при отмене после
    такого-то числа» гостю полезнее, чем общее «бесплатная отмена невозможна».
    """
    group = plan.get("cancel_penalty_group") or {}
    penalties = [
        str(p.get("description") or "").strip()
        for p in (group.get("cancel_penalties") or [])
    ]
    dated = next((p for p in penalties if p and "после" in p.casefold()), "")
    if dated:
        return dated
    if penalties and penalties[0]:
        return penalties[0]
    return str(group.get("description") or "").strip()
