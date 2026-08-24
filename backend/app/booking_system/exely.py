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

from .base import Availability, BookingSystemUnavailable, RoomOffer

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
        self._hotel = hotel_code
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

        return Availability(check_in, check_out, nights, self._offers(data), "exely")

    def _offers(self, data: dict[str, Any]) -> list[RoomOffer]:
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

        for stay in data.get("room_stays") or []:
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

        # Категории, которых в ответе не оказалось вовсе, свободными не
        # считаются: Exely присылает только то, что продаётся на эти даты.
        for slug in ROOM_TYPES.values():
            left.setdefault(slug, 0)

        return [
            RoomOffer(
                room_slug=slug,
                room_name=self.display(slug),
                rooms_left=count,
                price_per_night=None,
                source="exely",
            )
            for slug, count in sorted(left.items())
        ]

    # ─── Запись: сознательно не реализована ───

    async def get_booking(self, external_id: str):
        raise BookingSystemUnavailable(WRITE_NOT_READY)

    async def invoices(self, *, company_bin: str = "", external_id: str = ""):
        raise BookingSystemUnavailable(WRITE_NOT_READY)
