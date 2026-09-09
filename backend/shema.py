"""
Догнать схему базы: добавить колонки, которых в ней не хватает.

Обычно это делает сам сайт при запуске. Скрипт нужен там, где запуск до
этого не доходит: если приложение падает из-за недостающей колонки, оно
не может её и добавить. Ровно так лёг боевой бэкенд 2026-09-09 — все
запросы отвечали 500, включая вебхук WhatsApp, и бот молчал.

    ./.venv/Scripts/python.exe shema.py           # показать расхождения
    ./.venv/Scripts/python.exe shema.py --write   # добавить недостающее

Чтобы починить боевой сайт, запускать с боевой строкой подключения:

    export DATABASE_URL="$(grep '^DATABASE_URL=' .env.vercel | cut -d= -f2-)"
    ./.venv/Scripts/python.exe shema.py --write

────────────────────────────────────────────────────────────────────────
ЧТО ОН ДЕЛАЕТ И ЧЕГО НЕ ДЕЛАЕТ

Только добавляет колонки из `_LATE_COLUMNS` в `db.py`. Не удаляет, не
переименовывает, не меняет типы и не трогает данные. Лишние колонки в базе
показывает, но оставляет: они могли остаться от старой версии, и удалять
их вслепую — потерять данные.

Каждая колонка добавляется отдельно. У Postgres после ошибки транзакция
аборчена целиком, и без разделения одна неверная строка утащила бы за
собой все следующие — как это и произошло.
"""

from __future__ import annotations

import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import inspect, text  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.db import _LATE_COLUMNS  # noqa: E402


async def run(write: bool) -> int:
    async with engine.connect() as conn:
        живые = await conn.run_sync(
            lambda c: {
                t: {к["name"] for к in inspect(c).get_columns(t)}
                for t in inspect(c).get_table_names()
            }
        )

    нехватка: list[tuple[str, str]] = []
    for имя, таблица in Base.metadata.tables.items():
        есть = живые.get(имя)
        if есть is None:
            print(f"  таблицы нет целиком: {имя} — её создаст запуск сайта")
            continue
        for колонка in таблица.columns:
            if колонка.name not in есть:
                нехватка.append((имя, колонка.name))

    if not нехватка:
        print("\n  Схема в порядке: недостающих колонок нет.\n")
        return 0

    print(f"\n  Не хватает колонок: {len(нехватка)}\n")
    for таблица, колонка in нехватка:
        ddl = (_LATE_COLUMNS.get(таблица) or {}).get(колонка)
        if ddl:
            print(f"    {таблица}.{колонка}   →   {ddl}")
        else:
            print(f"    {таблица}.{колонка}   →   НЕТ В СПИСКЕ _LATE_COLUMNS, "
                  "добавить туда описание колонки")

    if not write:
        print("\n  Ничего не менялось. Для записи добавьте --write\n")
        return 1

    добавлено = 0
    for таблица, колонка in нехватка:
        ddl = (_LATE_COLUMNS.get(таблица) or {}).get(колонка)
        if not ddl:
            continue
        # Своей транзакцией на каждую: одна неудачная не должна отменять
        # остальные.
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"ALTER TABLE {таблица} ADD COLUMN {колонка} {ddl}"))
            print(f"    добавлена {таблица}.{колонка}")
            добавлено += 1
        except Exception as error:  # noqa: BLE001
            print(f"    НЕ ДОБАВИЛАСЬ {таблица}.{колонка}: "
                  f"{str(error).splitlines()[0][:140]}")

    print(f"\n  Добавлено колонок: {добавлено} из {len(нехватка)}\n")
    return 0 if добавлено == len(нехватка) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run("--write" in sys.argv)))
