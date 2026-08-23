"""
Локальная шахматка и окно переписки — для отладки в админке.

Пока настоящего Exely нет, единственный способ понять, правильно ли консьерж
ладит с базой, — видеть эту базу глазами и уметь её менять. Поставил бронь
руками в одной вкладке, спросил консьержа в другой: скажет ли он, что занято.

Эти эндпоинты живут отдельно от `corp_api` и от публичного API нарочно. Это
отладочная оснастка: когда шахматку заменит Exely, файл уйдёт целиком, и
ничего за собой не потянет.

Всё под админской авторизацией. Тут можно отменить чужую бронь и написать от
лица гостя — постороннему здесь делать нечего.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_admin
from .booking_system import get_booking_system
from .concierge import answer
from .config import Settings, get_settings
from .db import LocalBooking, LocalPayment, LocalStock, Room, get_session

router = APIRouter(
    prefix="/api/admin/local",
    tags=["admin: локальная шахматка"],
    dependencies=[Depends(require_admin)],
)


async def _room_names(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(Room))).scalars().all()
    return {room.slug: (room.short_name or room.name) for room in rows}


async def _system(settings: Settings, session: AsyncSession):
    booking = get_booking_system(settings, await _room_names(session))
    if booking is None or not hasattr(booking, "snapshot"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Локальная шахматка выключена. В backend/.env нужно BOOKING_SYSTEM=local",
        )
    return booking


class StockOut(BaseModel):
    roomSlug: str
    roomName: str
    roomsTotal: int


class BoardOut(BaseModel):
    """Всё, что нужно странице шахматки, одним запросом."""

    system: str
    stock: list[StockOut]
    bookings: list[dict]
    payments: list[dict]


class NewBooking(BaseModel):
    roomSlug: str = Field(min_length=1, max_length=60)
    roomsCount: int = Field(default=1, ge=1, le=40)
    checkIn: date
    checkOut: date
    guestName: str = Field(default="", max_length=200)
    guestPhone: str = Field(default="", max_length=40)
    amount: int = Field(default=0, ge=0, le=100_000_000)
    note: str = Field(default="", max_length=500)


class StockIn(BaseModel):
    roomSlug: str = Field(min_length=1, max_length=60)
    roomsTotal: int = Field(ge=0, le=500)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    #: Телефон, от лица которого пишем. По нему консьерж видит «свои» брони.
    phone: str = Field(default="+7 701 000 11 22", max_length=40)
    history: list[dict] = Field(default_factory=list)


@router.get("/board", response_model=BoardOut)
async def board(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    booking = await _system(settings, session)
    names = await _room_names(session)

    # Раскладка номеров по категориям на первом заходе: иначе страница
    # покажет пустой список, а это читается как «в отеле нет номеров».
    await booking.ensure_stock()

    stock_rows = (await session.execute(select(LocalStock))).scalars().all()
    payment_rows = (
        await session.execute(select(LocalPayment).order_by(LocalPayment.created_at.desc()))
    ).scalars().all()

    return BoardOut(
        system=booking.name,
        stock=[
            StockOut(
                roomSlug=row.room_slug,
                roomName=names.get(row.room_slug, row.room_slug),
                roomsTotal=row.rooms_total,
            )
            for row in sorted(stock_rows, key=lambda r: r.room_slug)
        ],
        bookings=await booking.snapshot(),
        payments=[
            {
                "bookingRef": p.booking_ref,
                "docNumber": p.doc_number,
                "amount": p.amount,
                "payer": p.payer,
                "createdAt": p.created_at.isoformat() if p.created_at else "",
            }
            for p in payment_rows
        ],
    )


@router.get("/availability")
async def availability(
    check_in: date,
    check_out: date,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    booking = await _system(settings, session)
    result = await booking.availability(check_in, check_out)
    return {
        "checkIn": result.check_in.isoformat(),
        "checkOut": result.check_out.isoformat(),
        "nights": result.nights,
        "offers": [
            {
                "roomSlug": offer.room_slug,
                "roomName": offer.room_name,
                "roomsLeft": offer.rooms_left,
            }
            for offer in result.offers
        ],
    }


@router.post("/bookings", status_code=status.HTTP_201_CREATED)
async def create(
    data: NewBooking,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    booking = await _system(settings, session)
    try:
        made = await booking.create_booking(
            room_slug=data.roomSlug,
            rooms_count=data.roomsCount,
            check_in=data.checkIn,
            check_out=data.checkOut,
            guest_name=data.guestName,
            guest_phone=data.guestPhone,
            amount=data.amount,
            origin="manual",
            note=data.note,
        )
    except Exception as error:  # noqa: BLE001 — текст ошибки полезен на странице
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    return {"ref": made.external_id}


@router.post("/bookings/{ref}/cancel")
async def cancel(
    ref: str,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    booking = await _system(settings, session)
    try:
        await booking.cancel_booking(ref, "отменено из админки")
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return {"ok": True}


@router.delete("/bookings/{ref}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(ref: str, session: AsyncSession = Depends(get_session)):
    """
    Стереть бронь совсем.

    Отмена оставляет след в шахматке — так и должно быть в жизни. Но при
    отладке нужен и способ убрать мусор, накопленный прогонами, иначе через
    неделю страница будет состоять из «Тест 1»…«Тест 40».
    """
    clean = ref.strip().upper()
    found = await session.execute(select(LocalBooking).where(LocalBooking.ref == clean))
    row = found.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Брони {ref} нет")
    await session.execute(delete(LocalPayment).where(LocalPayment.booking_ref == clean))
    await session.delete(row)
    await session.commit()


@router.patch("/stock")
async def set_stock(data: StockIn, session: AsyncSession = Depends(get_session)):
    found = await session.execute(
        select(LocalStock).where(LocalStock.room_slug == data.roomSlug)
    )
    row = found.scalar_one_or_none()
    if row is None:
        row = LocalStock(room_slug=data.roomSlug, rooms_total=data.roomsTotal)
        session.add(row)
    else:
        row.rooms_total = data.roomsTotal
    await session.commit()
    return {"ok": True}


@router.post("/chat")
async def chat(
    data: ChatIn,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    """
    Написать консьержу от лица гостя — то же, что придёт из WhatsApp.

    Телефон задаётся полем, а не берётся из сессии админа: именно по нему
    консьерж решает, чьи брони показывать, и подменить его — единственный
    способ проверить, что чужие он не отдаёт.
    """
    booking = get_booking_system(settings, await _room_names(session))
    reply = await answer(
        settings,
        message=data.message,
        history=data.history,
        today=date.today().isoformat(),
        booking=booking,
        guest={"phone": data.phone},
    )
    return {
        "text": reply["text"],
        "ok": reply["ok"],
        "reason": reply.get("reason", ""),
        "toolCalls": reply.get("toolCalls", []),
        "history": reply.get("messages", []),
        "usage": reply.get("usage", {}),
    }
