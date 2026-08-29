"""
Воронка для админки: докуда доходят гости, написавшие в WhatsApp.

Отдельный файл, а не строчка в существующем роутере: считается воронка по
переписке, а не по номерам или броням, и мешать её с ними — значит потом
искать её в чужом модуле.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_admin
from .db import get_session
from .funnel import DEFAULT_DAYS, report

router = APIRouter(
    prefix="/api/admin/funnel",
    tags=["admin: воронка"],
    dependencies=[Depends(require_admin)],
)


@router.get("")
async def funnel(
    days: int = Query(DEFAULT_DAYS, ge=1, le=180, description="За сколько дней считать"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Сколько человек написало, докуда дошли и кто застрял.

    Срок задаётся, потому что вопросы у отеля разные: «как прошла неделя» и
    «есть ли вообще толк за месяц» — это два разных числа, и подменять одно
    другим нельзя.
    """
    return await report(session, days)
