"""
Цены на сайте — как в Exely.

Зачем. 2026-10-05 выяснилось, что цены живут в трёх местах и все разные: прайс
ресепшена, тарифы Exely (через них гость платит) и сайт (админка). Владелец
решил: сайт показывает то же, что Exely. Цену в админке достаточно один раз не
поправить при смене тарифа — и гость видит на сайте одно, а в форме брони
другое. Поэтому цены переносятся сами, раз в день (daily-check.yml).

Какая цена «как в Exely». У тарифов со скидкой («Выгодные выходные», «Тариф
без завтрака») Exely отдаёт и прежнюю цену (was) — это и есть обычная цена
номера. Её и берём: скидки на конкретные даты консьерж называет по наличию.
Проверено 2026-10-05: Booking.com продаёт ровно по этим ценам плюс 12,5%
(Standart 35 000 → 39 375, Comfort на двоих 45 000 → 50 625).

Цены в Exely сезонные: на 2026-10-05 одноместный в октябре стоит 35 000, с
ноября 25 000. Сайт показывает то, что гость увидит сейчас, — цену на
ближайшую дату, на которую номер продаётся (отель бывает полным на неделю
вперёд, поэтому смотрим каждые три дня на полтора месяца). Сезон сменился —
на следующий день сменится и цена на сайте.

Договорные цены компаний от этого не зависят: у них цены прописаны по каждому
номеру (company_rates), от цены сайта считается только скидка в процентах.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Room

logger = logging.getLogger(__name__)

#: Через сколько дней от сегодня смотреть цены: каждые три дня на полтора
#: месяца. 15 дат на двух числах гостей — 30 запросов наличия, около 25 секунд.
SAMPLE_DAYS = tuple(range(1, 46, 3))


def base_price(rates: Any) -> int | None:
    """Обычная цена номера по тарифам одного предложения Exely.

    Прежняя цена у тарифа со скидкой (was) — то, что Exely зачёркивает.
    Если скидок на дату нет, обычной ценой считаем самый дорогой тариф.
    """
    def поле(тариф: Any, имя: str) -> Any:
        # Тариф приходит объектом (booking_system.base.Rate), в тестах — словарём.
        return тариф.get(имя) if isinstance(тариф, dict) else getattr(тариф, имя, None)

    прежние = [int(поле(r, "was")) for r in (rates or ()) if поле(r, "was")]
    if прежние:
        return max(прежние)
    цены = [int(поле(r, "price")) for r in (rates or ()) if поле(r, "price")]
    return max(цены) if цены else None


async def exely_prices(booking: Any, today: date) -> dict[str, dict[int, int]]:
    """Обычные цены Exely сейчас: {slug: {1: за одного, 2: за двоих}}.

    По каждому номеру — цена на ближайшую дату, на которую он продаётся.
    """
    out: dict[str, dict[int, int]] = {}
    for offset in SAMPLE_DAYS:
        day = today + timedelta(days=offset)
        for guests in (1, 2):
            try:
                result = await booking.availability(day, day + timedelta(days=1), guests=guests)
            except Exception as error:  # noqa: BLE001 — одна дата не повод бросать остальные
                logger.warning("Цены Exely на %s не получены: %s", day, error)
                continue
            for offer in result.offers:
                цена = base_price(getattr(offer, "rates", ()))
                if цена and guests not in out.get(offer.room_slug, {}):
                    out.setdefault(offer.room_slug, {})[guests] = цена
    return out


async def sync_prices(session: AsyncSession, booking: Any, *, today: date | None = None,
                      dry_run: bool = False) -> dict[str, Any]:
    """Поставить на сайте цены из Exely. dry_run — только показать, что изменится."""
    if today is None:
        from .almaty import today as hotel_today  # noqa: PLC0415

        today = hotel_today()
    prices = await exely_prices(booking, today)
    if not prices:
        return {"ok": False, "error": "Exely не отдал ни одной цены — на сайте ничего не меняю"}

    changes: list[dict[str, Any]] = []
    rooms = (await session.execute(select(Room))).scalars().all()
    for room in rooms:
        цены = prices.get(room.slug)
        if not цены:
            continue
        за_одного = цены.get(1) or цены.get(2)
        за_двоих = цены.get(2) or за_одного
        if room.capacity <= 1:
            # Одноместный: цены за двоих не бывает, храним ту же.
            за_двоих = за_одного
        было = (room.price, room.price_double or room.price)
        if (за_одного, за_двоих) == было:
            continue
        changes.append({"room": room.slug, "было": list(было), "стало": [за_одного, за_двоих]})
        if not dry_run:
            room.price = за_одного
            room.price_double = за_двоих
    if changes and not dry_run:
        await session.commit()
        logger.info("Цены сайта приведены к Exely: %s", changes)
    return {"ok": True, "dry_run": dry_run, "changes": changes, "exely": prices}
