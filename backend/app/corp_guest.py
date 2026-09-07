"""
Узнать корпоративного гостя по номеру телефона.

Зачем это нужно. У компании по договору свои цены: процент от прайса или
точная цена на категорию. В кабинете сотрудник их видит, а в WhatsApp — нет:
бот про компании не знал вовсе и называл прайс. Один и тот же номер стоил
разного в зависимости от того, где спросили, и объяснять эту разницу
приходилось менеджеру.

Мостик — телефон. Сотрудник компании заведён в кабинете вместе с телефоном,
а WhatsApp телефон знает всегда. Другого способа узнать гостя до того, как
он представится, нет.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ СОВПАДЕНИЕ ДОЛЖНО БЫТЬ ЕДИНСТВЕННЫМ

Ошибиться здесь можно в две стороны, и они неравноценны.

Не узнать своего — неприятно: сотрудник услышит прайс вместо договорной
цены, переспросит, менеджер поправит.

Принять чужого за своего — хуже: посторонний человек узнаёт условия чужого
договора, а это коммерческая тайна отеля и компании. Поэтому: только
активный сотрудник, только активная компания и только при ОДНОМ совпадении.
Два совпадения означают, что телефон записан двум людям, — тогда не
применяем ничего.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)

#: Сколько последних цифр сравнивать. Один и тот же номер пишут по-разному:
#: «+7 701 930 03 70», «8 701 9300370», «7019300370». Последние десять цифр
#: у всех этих записей одинаковые, а различить два разных казахстанских
#: номера по ним нельзя только в теории.
TAIL = 10


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _tail(value: Any) -> str:
    цифры = _digits(value)
    return цифры[-TAIL:] if len(цифры) >= TAIL else ""


async def find_corporate(phone: str) -> dict[str, Any] | None:
    """Компания, от имени которой пишет этот номер. None — обычный гость.

    Денег не двигает и ничего не пишет: только читает справочник компаний.
    """
    хвост = _tail(phone)
    if not хвост:
        return None

    from .db import Company, CompanyRate, CompanyUser, SessionLocal

    try:
        async with SessionLocal() as session:
            люди = (
                await session.execute(
                    select(CompanyUser)
                    .where(CompanyUser.is_active.is_(True))
                    .where(CompanyUser.phone != "")
                )
            ).scalars().all()

            # Сравниваем в Python, а не в SQL: в базе телефон лежит как его
            # ввёл менеджер, со скобками и пробелами, и LIKE по нему находит
            # не то. Сотрудников у корпоративных клиентов десятки, а не
            # тысячи — перебрать их дешевле, чем чистить данные запросом.
            свои = [ч for ч in люди if _tail(ч.phone) == хвост]
            if len(свои) != 1:
                if свои:
                    logger.info("Телефон совпал с %d сотрудниками — не применяем",
                                len(свои))
                return None

            человек = свои[0]
            компания = await session.get(Company, человек.company_id)
            if компания is None or not компания.is_active:
                return None

            тарифы = {
                строка.room_slug: строка.price
                for строка in (
                    await session.execute(
                        select(CompanyRate).where(
                            CompanyRate.company_id == компания.id)
                    )
                ).scalars().all()
            }
    except Exception as error:  # noqa: BLE001
        # Справочник недоступен — отвечаем как обычному гостю. Промолчать про
        # скидку хуже, чем не ответить вовсе, но ненамного: гость перепишется
        # с менеджером. А вот уронить ответ из-за необязательной справки —
        # потерять разговор целиком.
        logger.warning("Не удалось узнать корпоративного гостя: %s", error)
        return None

    return {
        "company": компания.name,
        "slug": компания.slug,
        "discount_percent": int(компания.discount_percent or 0),
        "rates": тарифы,
        "breakfast_price": int(компания.breakfast_price or 0),
        "payment_terms": компания.payment_terms or "",
        "manager_name": компания.manager_name or "",
        "manager_phone": компания.manager_phone or "",
        "person": человек.full_name or "",
    }


def price_for(corporate: dict[str, Any], room_slug: str, public_price: int) -> int:
    """Цена номера для этой компании. Та же формула, что в кабинете."""
    from .corp_api import corp_price

    return corp_price(
        public_price,
        int(corporate.get("discount_percent") or 0),
        (corporate.get("rates") or {}).get(room_slug),
    )
