"""
Договор с системой бронирования отеля.

Шахматка живёт не у нас: номерами и наличием заведует Exely, доступ к её API
отель пока не получил. Чтобы это не блокировало работу, весь обмен с внешней
системой сведён к одному интерфейсу. Сегодня за ним стоит заглушка, завтра —
настоящий Exely, и остальной код разницы не заметит.

Отдельно оговорено происхождение ответа: у каждого результата есть поле
`source`. Заглушка честно помечает себя `stub`, и всё, что показывает наличие
гостю, обязано это учитывать. Придуманное «номер свободен» — обещание, которое
отель не сможет сдержать, и цена такой ошибки выше, чем польза от красивой
демонстрации.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol, runtime_checkable

Source = Literal["stub", "exely"]


class BookingSystemUnavailable(RuntimeError):
    """Внешняя система не ответила или не настроена."""


@dataclass(frozen=True)
class RatePlan:
    """
    Один тариф на номер: по какой цене его сегодня продают.

    У отеля их несколько на одну и ту же категорию — с завтраком, без
    завтрака, акция выходного дня, — и цены отличаются заметно. Пока мы
    называли гостю только цену из прайса, он слышал число выше того, по
    которому реально может забронировать.
    """

    code: str
    name: str
    price: int
    #: Завтрак в цене. None — по названию тарифа не понять.
    breakfast: bool | None = None
    #: Цена без скидки, если тариф акционный.
    was: int | None = None


@dataclass(frozen=True)
class RoomOffer:
    """Что система бронирования говорит про один тип номера на выбранные даты."""

    room_slug: str
    room_name: str
    #: Сколько номеров этого типа свободно на весь запрошенный период.
    #: Ноль — свободных нет, None — система не смогла ответить по этому типу.
    rooms_left: int | None
    #: Цена за ночь в тенге по данным внешней системы. Может отличаться от
    #: цены на сайте: у отеля бывают сезонные тарифы, о которых мы не знаем.
    price_per_night: int | None
    source: Source
    #: Тарифы на эту категорию. Пусто — система их не отдаёт.
    rates: tuple[RatePlan, ...] = ()


@dataclass(frozen=True)
class Availability:
    check_in: date
    check_out: date
    nights: int
    offers: list[RoomOffer] = field(default_factory=list)
    source: Source = "stub"

    @property
    def anything_free(self) -> bool:
        return any((offer.rooms_left or 0) > 0 for offer in self.offers)


@dataclass(frozen=True)
class ExternalBooking:
    """Бронь глазами внешней системы."""

    external_id: str
    status: str
    check_in: date
    check_out: date
    total_amount: int
    guest_name: str
    source: Source


@dataclass(frozen=True)
class ExternalInvoice:
    """Счёт на оплату из внешней системы."""

    number: str
    issued_at: date
    due_at: date | None
    amount: int
    paid_amount: int
    status: str
    source: Source
    #: Ссылка на счёт в кабинете внешней системы, если она её отдаёт.
    url: str = ""

    @property
    def outstanding(self) -> int:
        return max(0, self.amount - self.paid_amount)


@runtime_checkable
class BookingSystem(Protocol):
    """
    Минимум, ради которого мы вообще идём во внешнюю систему.

    Список намеренно короткий. Всё, что можно посчитать у себя (корпоративные
    цены, история компании, отчёты), считается у себя: чужой API — самая
    хрупкая часть цепочки, и чем меньше на нём висит, тем меньше ломается.
    """

    name: str
    source: Source

    async def availability(self, check_in: date, check_out: date) -> Availability:
        """Свободные номера на период."""
        ...

    async def get_booking(self, external_id: str) -> ExternalBooking | None:
        """Состояние брони во внешней системе."""
        ...

    async def invoices(self, *, company_bin: str = "", external_id: str = "") -> list[ExternalInvoice]:
        """Счета на оплату: по БИН компании или по конкретной броне."""
        ...
