"""
Адаптер к Exely — пока каркас.

Доступа к API у отеля нет: запрос интеграторам отправлен, ответа на 2026-08-23
не было. Файл существует, чтобы место под настоящий обмен было размечено
заранее, а переход состоял из заполнения методов, а не из переделки всего,
что вокруг.

Что известно про интеграцию на сегодня (из виджета брони на сайте):
  - загрузчик виджета: kz-ibe.hopenapi.com
  - контекст: BE-INT-airisresidence_2026-08-13
  - код отеля: 509506
Это параметры фронтового виджета, не серверного API. Ключи, адрес API и
формат ответов придут от интеграторов — под них и заполняются методы ниже.
"""

from __future__ import annotations

from datetime import date

from .base import Availability, BookingSystemUnavailable, ExternalBooking, ExternalInvoice

#: Известные параметры виджета. Держим рядом, чтобы при разговоре с
#: интеграторами не искать их по коду фронтенда.
HOTEL_CODE = "509506"
WIDGET_CONTEXT = "BE-INT-airisresidence_2026-08-13"

NOT_READY = (
    "Доступ к API Exely не получен. Пока запрос висит у интеграторов, "
    "наличие номеров подтверждает менеджер отеля вручную."
)


class ExelyBookingSystem:
    """Настоящая система бронирования. Методы заполняются, когда придут ключи."""

    name = "Exely"
    source = "exely"

    def __init__(self, base_url: str, api_key: str, hotel_code: str = HOTEL_CODE) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._hotel_code = hotel_code

    async def availability(self, check_in: date, check_out: date) -> Availability:
        raise BookingSystemUnavailable(NOT_READY)

    async def get_booking(self, external_id: str) -> ExternalBooking | None:
        raise BookingSystemUnavailable(NOT_READY)

    async def invoices(
        self, *, company_bin: str = "", external_id: str = ""
    ) -> list[ExternalInvoice]:
        raise BookingSystemUnavailable(NOT_READY)
