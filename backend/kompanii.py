"""
Завести корпоративных клиентов с ценами из договора.

Цены взяты с прайс-листа, висящего на ресепшене (фото от 2026-09-09).
Скрипт заводит компании, их договорные цены и по одному ответственному с
доступом в кабинет `/corp`.

    ./.venv/Scripts/python.exe kompanii.py           # показать, что будет
    ./.venv/Scripts/python.exe kompanii.py --write   # записать в базу

Работает с той базой, что указана в окружении (`DATABASE_URL`). Чтобы
завести компании на боевом сайте, запускать с боевым значением.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ ЗАПУСКАТЬ МОЖНО ПОВТОРНО

Компании ищутся по короткому коду (`slug`). Уже заведённая компания не
дублируется: у неё обновляются название и цены.

**Пароль существующему сотруднику НЕ меняется.** Иначе второй запуск
незаметно выкинул бы из кабинета людей, которые уже им пользуются, — а
узналось бы это от них же, по телефону. Новый пароль печатается только для
тех, кого скрипт завёл сам.

────────────────────────────────────────────────────────────────────────
ЧЕГО ЗДЕСЬ НАМЕРЕННО НЕТ

**Телефонов ответственных.** Их нет в прайс-листе, а выдумывать нельзя:
по телефону бот узнаёт корпоративного гостя в WhatsApp, и чужой номер в
этом поле означал бы, что посторонний человек увидит цены чужого договора.
Пока поле пустое, бот отвечает сотруднику как обычному гостю — по прайсу.
Телефоны вписываются в админке, после чего связка заработает сама.

**Скидки процентом.** В договорах указаны точные цены по категориям, а не
процент. Точная цена и так важнее процента, а процент «на всё остальное»
никто не согласовывал: категории вне таблицы остаются вне договора, и
цену по ним называет менеджер.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

# Кириллица в консоли Windows: без этого вывод падает на первом же названии.
sys.stdout.reconfigure(encoding="utf-8")

import parol  # noqa: E402
from app.corp_auth import hash_password  # noqa: E402
from app.db import (  # noqa: E402
    Company,
    CompanyRate,
    CompanyUser,
    Room,
    SessionLocal,
)

#: Столбцы прайс-листа → коды категорий на сайте.
КОЛОНКИ = {
    "Одноместный Стандарт": "standart-single",
    "Двухместный Стандарт": "standart",
    "Твин": "standart-twin",
    "Комфорт": "comfort",
}

#: Договорные цены. Порядок значений — как в КОЛОНКИ.
КОМПАНИИ: list[dict[str, Any]] = [
    {"slug": "global-air", "name": "Глобал Эйр",
     "prices": [25000, 30000, 42000, 42000]},
    {"slug": "internet-truizm", "name": "Интернет Труизм",
     "prices": [25000, 30000, 42000, 42000]},
    {"slug": "tarlan", "name": "Тарлан",
     "prices": [20000, 25000, 35000, 38000]},
    {"slug": "rustar", "name": "Рустар",
     "prices": [30000, 32000, 42000, 42000]},
    {"slug": "kompas", "name": "Компас",
     "prices": [20000, 25000, 35000, 38000]},
]

#: Длина пароля. Двенадцати символов из набора без похожих букв достаточно,
#: а диктовать их по телефону партнёру ещё реально.
ДЛИНА_ПАРОЛЯ = 12


def логин(slug: str) -> str:
    """Логин для входа в кабинет.

    Выглядит как почта, потому что кабинет спрашивает почту, но почтовым
    ящиком не является: письма туда не ходят. Так удобнее диктовать и
    невозможно перепутать с личным адресом сотрудника.
    """
    return f"{slug}@airisresidence.kz"


async def прайс() -> dict[str, int]:
    """Публичные цены с сайта — чтобы посчитать, какая вышла скидка."""
    async with SessionLocal() as session:
        from sqlalchemy import select

        rooms = (await session.execute(select(Room))).scalars().all()
        return {str(r.slug): int(r.price or 0) for r in rooms}


async def run(write: bool) -> int:
    публичные = await прайс()
    выдача: list[tuple[str, str, str]] = []

    async with SessionLocal() as session:
        from sqlalchemy import select

        for запись in КОМПАНИИ:
            slug = запись["slug"]
            цены = dict(zip(КОЛОНКИ.values(), запись["prices"], strict=True))

            компания = (
                await session.execute(select(Company).where(Company.slug == slug))
            ).scalars().first()

            новая = компания is None
            if новая:
                компания = Company(slug=slug, name=запись["name"])
                session.add(компания)
                await session.flush()
            else:
                компания.name = запись["name"]
            компания.is_active = True

            print(f"\n  {запись['name']}  ({slug}) — "
                  f"{'заводим' if новая else 'обновляем'}")

            for код, цена in цены.items():
                прайсовая = публичные.get(код)
                строка = (
                    await session.execute(
                        select(CompanyRate)
                        .where(CompanyRate.company_id == компания.id)
                        .where(CompanyRate.room_slug == код)
                    )
                ).scalars().first()
                if строка is None:
                    session.add(CompanyRate(company_id=компания.id,
                                            room_slug=код, price=цена))
                else:
                    строка.price = цена

                if прайсовая:
                    разница = прайсовая - цена
                    доля = разница * 100 / прайсовая
                    знак = "скидка" if разница > 0 else "ДОРОЖЕ ПРАЙСА на"
                    print(f"      {код:<16} {цена:>6} ₸   "
                          f"прайс {прайсовая:>6} ₸   {знак} {abs(доля):.1f}%")
                else:
                    print(f"      {код:<16} {цена:>6} ₸   прайса нет")

            почта = логин(slug)
            человек = (
                await session.execute(
                    select(CompanyUser).where(CompanyUser.email == почта)
                )
            ).scalars().first()

            if человек is None:
                пароль = parol.make(ДЛИНА_ПАРОЛЯ)
                session.add(CompanyUser(
                    company_id=компания.id, email=почта,
                    password_hash=hash_password(пароль),
                    full_name=f"{запись['name']} — ответственный",
                    role="admin", is_active=True,
                ))
                выдача.append((запись["name"], почта, пароль))
            else:
                человек.company_id = компания.id
                человек.is_active = True
                выдача.append((запись["name"], почта, "(пароль прежний)"))

        if write:
            await session.commit()
            print("\n  Записано в базу.")
        else:
            await session.rollback()
            print("\n  Ничего не записано — это был показ. "
                  "Для записи добавьте --write")

    print("\n" + "─" * 68)
    print("  ДОСТУПЫ В КАБИНЕТ  https://airisresidence.kz/corp")
    print("─" * 68)
    for имя, почта, пароль in выдача:
        print(f"\n  {имя}")
        print(f"      логин:  {почта}")
        print(f"      пароль: {пароль}")
    print()

    if write:
        новые = [(и, п, пар) for и, п, пар in выдача if not пар.startswith("(")]
        for имя, почта, пароль in новые:
            parol.remember(пароль, f"кабинет /corp — {имя} ({почта})")
        if новые:
            print(f"  Пароли записаны в {parol.FILE} — файл вне git.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run("--write" in sys.argv)))
