"""
Локальная заглушка вместо Exely.

Нужна, чтобы доводить ИИ-консьержа и кабинет уже сейчас, не дожидаясь доступа
к чужому API. Заглушка отвечает на те же вопросы и в том же виде, что будет
отвечать настоящая система, — значит код, который её вызывает, потом менять
не придётся.

Занятость выдумана, но выдумана **воспроизводимо**: она выводится из даты и
кода номера через хеш, а не через случайное число. Один и тот же запрос всегда
даёт один и тот же ответ, иначе тесты на наличие мест были бы бесполезны, а
разговор с консьержем менялся бы между двумя одинаковыми вопросами.

Каждый ответ помечен `source="stub"`. Всё, что показывает наличие живому
гостю, обязано на это смотреть: заглушка годится для отладки, а не для
обещаний.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from .base import Availability, ExternalBooking, ExternalInvoice, RoomOffer

#: Сколько номеров каждого типа «есть у отеля» в заглушке.
#:
#: Цифры вымышленные и подобраны так, чтобы в сумме дать 34 номера с сайта.
#: Настоящая разбивка по категориям знает только Exely, и подменять её здесь
#: нельзя — при переходе на боевой API эта таблица уходит целиком.
STUB_INVENTORY: dict[str, int] = {
    "standart-single": 6,
    "standart": 12,
    "standart-twin": 8,
    "comfort": 5,
    "comfort-plus": 3,
}


def _occupied(room_slug: str, day: date) -> int:
    """
    Сколько номеров этого типа «занято» в этот день.

    Хеш от пары (номер, дата) — чтобы ответ был устойчивым между запросами и
    при этом разным для разных дат. Выходные загружаем сильнее: так заглушка
    ведёт себя похоже на настоящий отель, и сценарий «на субботу мест нет»
    можно проверить, не подкручивая данные вручную.
    """
    total = STUB_INVENTORY.get(room_slug, 0)
    if total == 0:
        return 0

    seed = f"{room_slug}:{day.isoformat()}".encode("utf-8")
    noise = int(hashlib.sha256(seed).hexdigest()[:8], 16)

    weekend = day.weekday() >= 4  # пятница и суббота
    ceiling = total if weekend else max(1, total - 1)
    return noise % (ceiling + 1)


class StubBookingSystem:
    """Ведёт себя как система бронирования, но данные придумывает сама."""

    name = "Локальная заглушка"
    source = "stub"

    def __init__(self, room_names: dict[str, str] | None = None) -> None:
        # Названия номеров приходят из нашей базы: заглушка не должна знать
        # ничего, чего не знает боевая система, но и выдумывать названия,
        # которых нет на сайте, ей незачем.
        self._names = room_names or {}

    async def availability(self, check_in: date, check_out: date) -> Availability:
        nights = (check_out - check_in).days
        if nights <= 0:
            return Availability(check_in, check_out, 0, [], "stub")

        offers: list[RoomOffer] = []
        for slug, total in STUB_INVENTORY.items():
            # Номер свободен на весь период, только если он свободен каждую
            # ночь. Берём худшую ночь — так же считает любая шахматка.
            worst = min(
                total - _occupied(slug, check_in + timedelta(days=i)) for i in range(nights)
            )
            offers.append(
                RoomOffer(
                    room_slug=slug,
                    room_name=self._names.get(slug, slug),
                    rooms_left=max(0, worst),
                    price_per_night=None,  # цену заглушка не выдумывает: она наша
                    source="stub",
                )
            )

        return Availability(check_in, check_out, nights, offers, "stub")

    async def get_booking(self, external_id: str) -> ExternalBooking | None:
        return None

    async def invoices(
        self, *, company_bin: str = "", external_id: str = ""
    ) -> list[ExternalInvoice]:
        # Счета отель выставляет сам, у нас они уже есть в корпоративной части.
        # Заглушка не подсовывает выдуманные суммы к оплате: увидев их в
        # кабинете, бухгалтерия компании может по ним и заплатить.
        return []
