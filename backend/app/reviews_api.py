"""
Отзывы гостей, оставленные на сайте отеля.

Попросил владелец 2026-10-05: гость должен мочь написать отзыв прямо на
сайте, и отзыв должен где-то храниться.

**Сначала проверка, потом сайт.** Отзыв ложится со статусом «на проверке» и
появляется на сайте, только когда сотрудник опубликует его в админке
(/admin/otzyvy). Открытая форма без проверки за неделю обрастает рекламой и
оскорблениями — и это видят гости на главной.

**Не для поисковиков.** Google не засчитывает отзывы, которые компания
собирает на своём сайте, поэтому разметку рейтинга не ставим. Отзывы на
сайте — для гостя, который выбирает; для карт его просим написать в 2ГИС,
Яндекс или TripAdvisor (кнопки рядом с формой).

**Контакт гостя не публикуется** — он нужен отелю, чтобы ответить на жалобу.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_admin
from .db import SiteReview, get_session
from .schemas import ReviewAdminOut, ReviewIn, ReviewOut, ReviewStatusIn
from .throttle import client_ip, too_many

logger = logging.getLogger(__name__)

public = APIRouter(prefix="/api/reviews", tags=["reviews"])
admin = APIRouter(
    prefix="/api/admin/reviews",
    tags=["admin: отзывы"],
    dependencies=[Depends(require_admin)],
)

#: Сколько отзывов можно оставить с одного адреса за час. Гость пишет один;
#: больше — уже рассылка.
PER_IP_PER_HOUR = 3


@public.post("", status_code=201)
async def create_review(payload: ReviewIn, request: Request,
                        session: AsyncSession = Depends(get_session)) -> dict:
    """Принять отзыв с сайта. Он ждёт проверки и на сайте пока не виден."""
    # Поле-ловушка: человек его не видит. Отвечаем успехом, чтобы бот не
    # подбирал обход.
    if payload.website:
        return {"ok": True}
    ip = client_ip(request)
    if too_many(f"review:{ip}", limit=PER_IP_PER_HOUR, window=3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Слишком много отзывов подряд. Попробуйте позже.")

    review = SiteReview(
        name=payload.name.strip(),
        text=payload.text.strip(),
        stars=payload.stars,
        stay=(payload.stay or "").strip(),
        contact=(payload.contact or "").strip(),
        ip=ip[:64],
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)

    # Сотрудник должен узнать сразу: жалобу на сайте лучше разобрать, пока
    # гость ещё в отеле. Сбой уведомления отзыв не теряет — он уже в базе.
    try:
        from .notify import _tell_hotel  # noqa: PLC0415 — notify тянет каналы

        звёзды = "★" * review.stars + "☆" * (5 - review.stars)
        await _tell_hotel(
            "📝 Новый отзыв на сайте — ждёт проверки\n\n"
            f"{звёзды} {review.name}"
            + (f", {review.stay}" if review.stay else "")
            + f"\n«{review.text[:500]}»"
            + (f"\nКонтакт: {review.contact}" if review.contact else "")
            + "\n\nОпубликовать или скрыть: airisresidence.kz/admin/otzyvy",
            "отзыв на сайте")
    except Exception as error:  # noqa: BLE001
        logger.warning("Отель не узнал об отзыве %s: %s", review.id, error)
    return {"ok": True, "id": review.id}


@public.get("", response_model=list[ReviewOut])
async def list_reviews(session: AsyncSession = Depends(get_session)):
    """Опубликованные отзывы — это читает сайт. Свежие сверху."""
    rows = await session.execute(
        select(SiteReview).where(SiteReview.status == "published")
        .order_by(SiteReview.created_at.desc()).limit(30)
    )
    return list(rows.scalars().all())


@admin.get("", response_model=list[ReviewAdminOut])
async def admin_list_reviews(session: AsyncSession = Depends(get_session)):
    """Все отзывы для проверки: новые сверху."""
    rows = await session.execute(
        select(SiteReview).order_by(SiteReview.created_at.desc()).limit(300))
    return list(rows.scalars().all())


@admin.patch("/{review_id}", response_model=ReviewAdminOut)
async def admin_set_status(review_id: int, payload: ReviewStatusIn,
                           session: AsyncSession = Depends(get_session)):
    """Опубликовать, скрыть или вернуть на проверку."""
    review = await session.get(SiteReview, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Отзыв не найден")
    review.status = payload.status
    await session.commit()
    await session.refresh(review)
    return review


@admin.delete("/{review_id}", status_code=204)
async def admin_delete_review(review_id: int, session: AsyncSession = Depends(get_session)):
    """Удалить совсем — для спама. Настоящий отзыв лучше скрыть."""
    review = await session.get(SiteReview, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Отзыв не найден")
    await session.delete(review)
    await session.commit()
