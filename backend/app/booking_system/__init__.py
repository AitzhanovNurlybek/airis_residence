"""
Выбор системы бронирования.

По умолчанию — никакой. Это не лень, а осознанная позиция: пока настоящего
API нет, честнее отвечать «наличие подтвердит стойка», чем показывать гостю
цифры из заглушки. Заглушка включается только явной настройкой
`BOOKING_SYSTEM`:
  пусто    — не подключена, наличие подтверждает стойка;
  `hybrid` — рабочая схема: наличие из Exely, брони заявками менеджеру;
  `exely`  — только чтение наличия, без записи;
  `local`  — учебная шахматка в нашей базе, для отладки записи;
  `stub`   — старая заглушка на хеше, без базы.
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
from .hybrid import HybridBookingSystem
from .local import (
    DEFAULT_STOCK,
    BookingNotFound,
    LocalBookingSystem,
    NotEnoughRooms,
)
from .stub import STUB_INVENTORY, StubBookingSystem

__all__ = [
    "Availability",
    "BookingSystem",
    "BookingNotFound",
    "BookingSystemUnavailable",
    "DEFAULT_STOCK",
    "LocalBookingSystem",
    "NotEnoughRooms",
    "ExelyBookingSystem",
    "HybridBookingSystem",
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

    if mode == "local":
        # Настоящая шахматка в нашей базе: с ней можно не только смотреть
        # наличие, но и заводить, менять и отменять брони.
        from ..db import SessionLocal

        return LocalBookingSystem(SessionLocal, room_names)

    if mode == "stub":
        # Старая заглушка на хеше: только чтение, зато без базы. Осталась для
        # быстрых проверок, где заводить таблицы незачем.
        return StubBookingSystem(room_names)

    if mode == "exely":
        # Только чтение: наличие с открытого адреса виджета. Записывать через
        # него не будем — для этого нужен договорной доступ.
        # Чтение броней подключается, только когда выдан договорной доступ.
        # Без него консьерж работает как раньше: наличие видит, брони — нет.
        reservations = None
        if settings.exely_api_ready:
            from .exely_api import ExelyApi

            reservations = ExelyApi(
                settings.exely_client_id,
                settings.exely_client_secret,
                settings.exely_property_id,
                auth_url=settings.exely_auth_url,
                api_base=settings.exely_api_base,
                # Обычно токен и бронь приходят меньше чем за секунду, но
                # Exely изредка притормаживает, и на 15 секундах гость
                # получал «не получается связаться с системой» вместо своей
                # брони. Запас дешевле: лишние секунды ожидания заметны
                # меньше, чем отказ.
                timeout=30.0,
            )

        return ExelyBookingSystem(
            hotel_code=settings.exely_hotel_code or "509506",
            room_names=room_names,
            reservations=reservations,
        )

    if mode == "hybrid":
        # Рабочая схема на сегодня: наличие настоящее, бронь уходит заявкой
        # менеджеру. Именно её ставят на боевой сайт, пока нет записи в Exely.
        from ..db import SessionLocal

        return HybridBookingSystem(
            SessionLocal, room_names, settings.exely_hotel_code or "509506"
        )

    return None
