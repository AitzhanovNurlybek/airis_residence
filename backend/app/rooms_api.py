"""Номера: публичное чтение и редактирование из админки."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_admin
from .config import Settings, get_settings
from .db import Room, get_session
from .media import delete_room_image, save_room_image
from .schemas import RoomIn, RoomOut, RoomPatch

logger = logging.getLogger(__name__)

public = APIRouter(prefix="/api/rooms", tags=["rooms"])
admin = APIRouter(
    prefix="/api/admin/rooms",
    tags=["admin: номера"],
    dependencies=[Depends(require_admin)],
)


async def _get(session: AsyncSession, slug: str) -> Room:
    result = await session.execute(select(Room).where(Room.slug == slug))
    room = result.scalar_one_or_none()
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Номер не найден")
    return room


# ────────────────────────── Публично ──────────────────────────


@public.get("", response_model=list[RoomOut])
async def list_rooms(session: AsyncSession = Depends(get_session)):
    """Опубликованные номера в заданном порядке — это читает сайт."""
    result = await session.execute(
        select(Room).where(Room.is_published.is_(True)).order_by(Room.sort_order, Room.id)
    )
    return list(result.scalars().all())


@public.get("/{slug}", response_model=RoomOut)
async def get_room(slug: str, session: AsyncSession = Depends(get_session)):
    room = await _get(session, slug)
    if not room.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Номер не найден")
    return room


# ────────────────────────── Админка ──────────────────────────


@admin.get("", response_model=list[RoomOut])
async def admin_list_rooms(session: AsyncSession = Depends(get_session)):
    """Все номера, включая скрытые."""
    result = await session.execute(select(Room).order_by(Room.sort_order, Room.id))
    return list(result.scalars().all())


@admin.get("/{slug}", response_model=RoomOut)
async def admin_get_room(slug: str, session: AsyncSession = Depends(get_session)):
    return await _get(session, slug)


@admin.post("", response_model=RoomOut, status_code=201)
async def create_room(payload: RoomIn, session: AsyncSession = Depends(get_session)):
    exists = await session.execute(select(Room).where(Room.slug == payload.slug))
    if exists.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Номер с кодом «{payload.slug}» уже есть"
        )

    last = await session.execute(select(Room).order_by(Room.sort_order.desc()).limit(1))
    tail = last.scalar_one_or_none()

    room = Room(
        slug=payload.slug,
        name=payload.name,
        short_name=payload.shortName,
        price=payload.price,
        area=payload.area,
        capacity=payload.capacity,
        beds=payload.beds,
        summary=payload.summary,
        description=payload.description,
        features=payload.features,
        images=[],
        sort_order=(tail.sort_order + 1) if tail else 0,
        is_published=False,  # новый номер публикуется вручную, после фото
    )
    session.add(room)
    await session.commit()
    await session.refresh(room)
    return room


@admin.patch("/{slug}", response_model=RoomOut)
async def update_room(
    slug: str, payload: RoomPatch, session: AsyncSession = Depends(get_session)
):
    room = await _get(session, slug)

    fields = {
        "name": "name",
        "shortName": "short_name",
        "price": "price",
        "area": "area",
        "capacity": "capacity",
        "beds": "beds",
        "summary": "summary",
        "description": "description",
        "features": "features",
        "images": "images",
        "sortOrder": "sort_order",
        "isPublished": "is_published",
    }
    data = payload.model_dump(exclude_unset=True)
    for key, column in fields.items():
        if key in data and data[key] is not None:
            setattr(room, column, data[key])

    await session.commit()
    await session.refresh(room)
    return room


@admin.delete("/{slug}", status_code=204)
async def delete_room(
    slug: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    room = await _get(session, slug)
    for url in room.images or []:
        delete_room_image(settings, url)
    await session.delete(room)
    await session.commit()


@admin.post("/{slug}/images", response_model=RoomOut)
async def upload_images(
    slug: str,
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Загрузка одной или нескольких фотографий. Добавляются в конец списка."""
    room = await _get(session, slug)

    saved: list[str] = []
    for upload in files:
        saved.append(await save_room_image(settings, slug, upload))

    # JSON-колонку нужно переприсвоить целиком, иначе SQLAlchemy
    # не заметит изменения списка и ничего не сохранит.
    room.images = [*(room.images or []), *saved]
    await session.commit()
    await session.refresh(room)
    return room


@admin.put("/{slug}/images", response_model=RoomOut)
async def set_images(
    slug: str,
    images: list[str],
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """
    Новый порядок фотографий. Первая в списке — обложка.
    Всё, что пропало из списка, удаляется и с диска.
    """
    room = await _get(session, slug)
    removed = [url for url in (room.images or []) if url not in images]
    for url in removed:
        delete_room_image(settings, url)

    room.images = images
    await session.commit()
    await session.refresh(room)
    return room


@admin.post("/reorder", response_model=list[RoomOut])
async def reorder_rooms(slugs: list[str], session: AsyncSession = Depends(get_session)):
    """Порядок номеров на сайте — так, как они перечислены."""
    result = await session.execute(select(Room))
    rooms = {room.slug: room for room in result.scalars().all()}

    for index, slug in enumerate(slugs):
        room = rooms.get(slug)
        if room is not None:
            room.sort_order = index

    await session.commit()
    ordered = await session.execute(select(Room).order_by(Room.sort_order, Room.id))
    return list(ordered.scalars().all())
