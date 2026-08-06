"""
Видеообзоры, не привязанные к номерам: кухня, лобби, общие зоны.

Загрузка устроена так же, как у номеров (временная ссылка, браузер
грузит файл прямо в хранилище, мы проверяем результат) — вся общая
часть лежит в video.py, здесь только про сущность.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_admin
from .config import Settings, get_settings
from .db import SiteVideo, get_session
from .schemas import (
    SiteVideoIn,
    SiteVideoOut,
    SiteVideoPatch,
    VideoConfirmIn,
    VideoSignIn,
    VideoSignOut,
)
from .video import (
    build_upload,
    delete_video,
    folder_for,
    save_video_through_api,
    verify_poster,
    verify_uploaded,
)

logger = logging.getLogger(__name__)

public = APIRouter(prefix="/api/site-videos", tags=["site videos"])
admin = APIRouter(
    prefix="/api/admin/site-videos",
    tags=["admin: видео на сайте"],
    dependencies=[Depends(require_admin)],
)


async def _get(session: AsyncSession, slug: str) -> SiteVideo:
    result = await session.execute(select(SiteVideo).where(SiteVideo.slug == slug))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Видео не найдено")
    return item


def _folder(slug: str) -> str:
    return folder_for("site", slug)


# ────────────────────────── Публично ──────────────────────────


@public.get("", response_model=list[SiteVideoOut])
async def list_videos(session: AsyncSession = Depends(get_session)):
    """Опубликованные ролики с уже загруженным файлом — это читает сайт."""
    result = await session.execute(
        select(SiteVideo)
        .where(SiteVideo.is_published.is_(True), SiteVideo.video != "")
        .order_by(SiteVideo.sort_order, SiteVideo.id)
    )
    return list(result.scalars().all())


# ────────────────────────── Админка ──────────────────────────


@admin.get("", response_model=list[SiteVideoOut])
async def admin_list(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SiteVideo).order_by(SiteVideo.sort_order, SiteVideo.id)
    )
    return list(result.scalars().all())


@admin.post("", response_model=SiteVideoOut, status_code=201)
async def create_video(payload: SiteVideoIn, session: AsyncSession = Depends(get_session)):
    exists = await session.execute(select(SiteVideo).where(SiteVideo.slug == payload.slug))
    if exists.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Видео с кодом «{payload.slug}» уже есть"
        )

    last = await session.execute(
        select(SiteVideo).order_by(SiteVideo.sort_order.desc()).limit(1)
    )
    tail = last.scalar_one_or_none()

    item = SiteVideo(
        slug=payload.slug,
        title=payload.title,
        summary=payload.summary,
        sort_order=(tail.sort_order + 1) if tail else 0,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@admin.patch("/{slug}", response_model=SiteVideoOut)
async def update_video(
    slug: str, payload: SiteVideoPatch, session: AsyncSession = Depends(get_session)
):
    item = await _get(session, slug)

    fields = {
        "title": "title",
        "summary": "summary",
        "sortOrder": "sort_order",
        "isPublished": "is_published",
    }
    data = payload.model_dump(exclude_unset=True)
    for key, column in fields.items():
        if key in data and data[key] is not None:
            setattr(item, column, data[key])

    await session.commit()
    await session.refresh(item)
    return item


@admin.delete("/{slug}", status_code=204)
async def delete_site_video(
    slug: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    item = await _get(session, slug)
    delete_video(settings, item.video)
    delete_video(settings, item.video_poster)
    await session.delete(item)
    await session.commit()


# ────────────────────────── Файл ролика ──────────────────────────


@admin.post("/{slug}/video/sign", response_model=VideoSignOut)
async def sign_upload(
    slug: str,
    payload: VideoSignIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    await _get(session, slug)

    upload = build_upload(settings, _folder(slug), payload.contentType, payload.sizeBytes)
    if upload is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Хранилище не выдаёт ссылки на прямую загрузку",
        )

    key, url, poster_key, poster_url = upload
    return VideoSignOut(
        uploadUrl=url,
        key=key,
        contentType=payload.contentType,
        maxBytes=settings.max_video_mb * 1024 * 1024,
        posterUploadUrl=poster_url,
        posterKey=poster_key,
    )


@admin.post("/{slug}/video/confirm", response_model=SiteVideoOut)
async def confirm_upload(
    slug: str,
    payload: VideoConfirmIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    item = await _get(session, slug)
    url = verify_uploaded(settings, _folder(slug), payload.key)
    poster = verify_poster(settings, _folder(slug), payload.posterKey)

    previous, previous_poster = item.video, item.video_poster
    item.video = url
    item.video_poster = poster
    await session.commit()
    await session.refresh(item)

    if previous and previous != url:
        delete_video(settings, previous)
    if previous_poster and previous_poster != poster:
        delete_video(settings, previous_poster)
    return item


@admin.post("/{slug}/video", response_model=SiteVideoOut)
async def upload_video(
    slug: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Запасной путь для площадок без временных ссылок."""
    item = await _get(session, slug)
    url = await save_video_through_api(settings, _folder(slug), file)

    previous, previous_poster = item.video, item.video_poster
    item.video = url
    item.video_poster = ""
    await session.commit()
    await session.refresh(item)

    if previous and previous != url:
        delete_video(settings, previous)
    delete_video(settings, previous_poster)
    return item


@admin.delete("/{slug}/video", response_model=SiteVideoOut)
async def remove_video(
    slug: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    item = await _get(session, slug)
    previous, previous_poster = item.video, item.video_poster

    item.video = ""
    item.video_poster = ""
    await session.commit()
    await session.refresh(item)

    delete_video(settings, previous)
    delete_video(settings, previous_poster)
    return item
