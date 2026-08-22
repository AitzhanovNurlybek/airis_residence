"""
Выбор системы бронирования.

По умолчанию — никакой. Это не лень, а осознанная позиция: пока настоящего
API нет, честнее отвечать «наличие подтвердит стойка», чем показывать гостю
цифры из заглушки. Заглушка включается только явной настройкой
`BOOKING_SYSTEM=stub` и нужна для отладки консьержа, а не для боевого сайта.
"""

from __future__ import annotations

from ..config import Settings
from .base import (
    Availability,
    BookingSystem,
    BookingSystemUnavailable,
    ExternalBooking,
    ExternalInvoice,
    RoomOffer,
)
from .exely import ExelyBookingSystem
from .stub import STUB_INVENTORY, StubBookingSystem

__all__ = [
    "Availability",
    "BookingSystem",
    "BookingSystemUnavailable",
    "ExelyBookingSystem",
    "ExternalBooking",
    "ExternalInvoice",
    "RoomOffer",
    "STUB_INVENTORY",
    "StubBookingSystem",
    "get_booking_system",
]


def get_booking_system(
    settings: Settings, room_names: dict[str, str] | None = None
) -> BookingSystem | None:
    """Возвращает адаптер или None, если система бронирования не подключена."""
    mode = (settings.booking_system or "").strip().lower()

    if mode == "stub":
        return StubBookingSystem(room_names)

    if mode == "exely":
        if not (settings.exely_base_url and settings.exely_api_key):
            return None
        return ExelyBookingSystem(
            settings.exely_base_url, settings.exely_api_key, settings.exely_hotel_code
        )

    return None
