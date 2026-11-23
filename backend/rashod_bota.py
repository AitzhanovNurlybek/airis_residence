"""
Сколько раз бот обращался к модели и за что — по боевой базе.

Без имён и телефонов, ничего не пишет. Нужен, когда кажется, что Anthropic
стоит дорого: показывает, какие части бота зовут модель и как часто.
Разбор 2026-11-23 этим же способом нашёл главную утечку — дожим спрашивал
модель о той же паузе каждый час (см. docs/МОНИТОРИНГ.md, «Расход на модель»).

Запуск из backend/ (база — из .env.vercel, рядом с этим файлом):
    python rashod_bota.py 30
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
for line in open(os.path.join(HERE, ".env.vercel"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")
sys.path.insert(0, HERE)

from sqlalchemy import func, select  # noqa: E402

from app.db import ChannelReceipt, DialogFollowup, DialogMessage, SessionLocal  # noqa: E402

STAFF = "[Ответил сотрудник отеля] "
NOTE = "[Сообщение отеля] "
ALMATY = timedelta(hours=5)


def kind(role: str, content: str) -> str:
    """Что за строка истории: вызов модели, реплика гостя, сотрудник, служебное."""
    if role == "assistant":
        if content.startswith(STAFF):
            return "сотрудник"
        if content.startswith(NOTE):
            return "отель"
        try:
            blocks = json.loads(content)
        except ValueError:
            blocks = None
        if isinstance(blocks, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_use" for b in blocks):
            return "круг"
        return "ответ"
    try:
        blocks = json.loads(content)
    except ValueError:
        blocks = None
    if isinstance(blocks, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
        return "результат"
    return "файл" if content.startswith("[Гость прислал") else "гость"


async def main(days: int) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(DialogMessage.created_at, DialogMessage.role, DialogMessage.content)
            .where(DialogMessage.channel == "whatsapp")
            .where(DialogMessage.created_at >= since)
            .order_by(DialogMessage.created_at))).all()
        sent = (await session.execute(
            select(func.count()).select_from(DialogFollowup)
            .where(DialogFollowup.sent_at >= since))).scalar() or 0
        declined = (await session.execute(
            select(func.count()).select_from(ChannelReceipt)
            .where(ChannelReceipt.channel == "followup")
            .where(ChannelReceipt.created_at >= since))).scalar() or 0

    by_week: dict[object, Counter] = defaultdict(Counter)
    guests: list[datetime] = []
    for when, role, content in rows:
        what = kind(role, content or "")
        day = (when + ALMATY).date()
        by_week[day - timedelta(days=day.weekday())][what] += 1
        if what in ("гость", "файл"):
            guests.append(when)

    total = Counter()
    for counts in by_week.values():
        total.update(counts)
    calls = total["ответ"] + total["круг"]
    print(f"За {days} дн.: обращений консьержа к модели {calls} "
          f"(ответов {total['ответ']}, кругов с инструментами {total['круг']}), "
          f"прочитано файлов {total['файл']}")
    print(f"Дожим: отправлено {sent}, решений «не писать» {declined} — "
          f"всего обращений ≈{sent + declined}")
    print("\nПо неделям (пн): реплик гостей / ответов / кругов / файлов / сотрудник")
    for week in sorted(by_week):
        c = by_week[week]
        print(f"  {week}: {c['гость']:4d} / {c['ответ']:4d} / {c['круг']:4d} / "
              f"{c['файл']:3d} / {c['сотрудник']:3d}")

    gaps = [(b - a).total_seconds() for a, b in zip(guests, guests[1:])]
    if gaps:
        n = len(gaps)
        print(f"\nКеш промпта: реплика гостя пришла в пределах 5 мин от предыдущей (любого "
              f"гостя) — {sum(g < 300 for g in gaps) / n:.0%}, в пределах часа — "
              f"{sum(g < 3600 for g in gaps) / n:.0%}")
    if not total["ответ"] and total["сотрудник"]:
        print("\n⚠️ Ответов бота нет, а сотрудники пишут: похоже, бот не отвечает "
              "(кончились кредиты Anthropic?).")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 30))
