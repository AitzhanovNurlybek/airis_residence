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

from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_admin
from .booking_system import BookingSystemUnavailable, ExelyBookingSystem, get_booking_system
from .booking_system.exely import NAMES as EXELY_NAMES
from .concierge import answer
from .config import Settings, get_settings
from .db import LocalBooking, LocalPayment, LocalStock, Room, get_session
from .knowledge import KnowledgeUnavailable, load_facts
from .payment_docs import MAX_DOC_MB, check_recipient, match_and_apply, read_document
from .almaty import today as hotel_today

router = APIRouter(
    prefix="/api/admin/local",
    tags=["admin: локальная шахматка"],
    dependencies=[Depends(require_admin)],
)


async def _room_names(session: AsyncSession) -> dict[str, str]:
    """
    Названия категорий для показа.

    Основа — номера сайта. Но отель продаёт в Exely и то, чего на сайте нет
    (Apart), и такая категория показывалась голым кодом. Подставляем название
    из Exely: код в интерфейсе выглядит поломкой, а это не поломка, а
    незаведённая на сайте категория.
    """
    rows = (await session.execute(select(Room))).scalars().all()
    names = {room.slug: (room.short_name or room.name) for room in rows}
    for slug, title in EXELY_NAMES.items():
        names.setdefault(slug, title)
    return names


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
        today=hotel_today().isoformat(),
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


@router.post("/payment")
async def payment(
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    """
    Разобрать присланный чек и, если всё сходится, отметить оплату.

    Загрузка идёт тем же полем `files`, что и фотографии номеров, — чтобы
    работал общий клиентский хелпер и не заводить второй способ отправки
    файлов ради одной страницы.

    Факты об отеле нужны для главной проверки: сверки получателя платежа с
    реквизитами. Если справка не загрузилась, разбор всё равно идёт, но
    отметить оплату сам он уже не может — проверить, нам ли деньги, нечем.
    """
    booking = await _system(settings, session)
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл не приложен")

    upload = files[0]
    data = await upload.read()
    if len(data) > MAX_DOC_MB * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Файл больше {MAX_DOC_MB} МБ — вряд ли это квитанция",
        )

    try:
        facts = await load_facts(settings)
    except KnowledgeUnavailable:
        facts = None

    try:
        doc = await read_document(settings, data, upload.filename or "document.pdf")
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Не удалось прочитать: {error}") from error

    # Без справки об отеле сверить получателя не с чем, а без этого отмечать
    # оплату нельзя: деньги могли уйти кому угодно.
    result = await match_and_apply(booking, doc, facts=facts, auto_apply=facts is not None)
    recipient, why = check_recipient(doc, facts)

    return {
        "verdict": result.verdict,
        "reason": result.reason,
        "bookingRef": result.booking_ref,
        "appliedAmount": result.applied_amount,
        "recipient": {"status": recipient, "note": why},
        "doc": {
            "isPayment": doc.is_payment,
            "payer": doc.payer,
            "payerBin": doc.payer_bin,
            "payee": doc.payee,
            "payeeBin": doc.payee_bin,
            "payeeAccount": doc.payee_account,
            "amount": doc.amount,
            "amountInWords": doc.amount_in_words,
            "currency": doc.currency,
            "paidAt": doc.paid_at,
            "purpose": doc.purpose,
            "reference": doc.reference,
            "bank": doc.bank,
            "docNumber": doc.doc_number,
            "statusWords": doc.status_words,
            "redFlags": doc.red_flags,
            "looksEdited": doc.looks_edited,
        },
    }


@router.get("/exely")
async def exely_availability(
    check_in: date,
    check_out: date,
    session: AsyncSession = Depends(get_session),
):
    """
    Настоящее наличие из Exely — то же, что видит гость в форме брони.

    Отдельно от учебной шахматки нарочно: рядом на странице их видно вместе, и
    сразу понятно, где выдуманные числа, а где настоящие. Запись сюда не
    ходит — Exely мы только читаем.
    """
    exely = ExelyBookingSystem(room_names=await _room_names(session))
    try:
        result = await exely.availability(check_in, check_out)
    except BookingSystemUnavailable as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error

    return {
        "checkIn": result.check_in.isoformat(),
        "checkOut": result.check_out.isoformat(),
        "nights": result.nights,
        "offers": [
            {
                "roomSlug": o.room_slug,
                "roomName": o.room_name,
                "roomsLeft": o.rooms_left,
            }
            for o in result.offers
        ],
    }


@router.get("/prices")
async def price_check(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    """
    Сколько стоит номер на сайте и почём он на самом деле продаётся.

    Цена живёт в двух местах: у нас в админке и в тарифах Exely. Синхронизации
    между ними нет никакой, и разойтись они могут молча — что и произошло:
    сайт показывает на несколько тысяч дороже того, по чему гость бронирует.
    Дороже, а не дешевле, поэтому никто не жалуется — просто часть гостей
    уходит, не открыв форму.

    Смотрим на неделю вперёд, а не на завтра: на ближайшие даты половина
    категорий распродана, и сравнивать было бы не с чем.
    """
    ours = {room.slug: room for room in (await session.execute(select(Room))).scalars().all()}
    exely = ExelyBookingSystem(room_names=await _room_names(session))

    check_in = hotel_today() + timedelta(days=7)
    try:
        live = await exely.availability(check_in, check_in + timedelta(days=1))
        offers = {o.room_slug: o for o in live.offers}
        reachable = True
    except BookingSystemUnavailable:
        offers, reachable = {}, False

    rows = []
    for slug, room in sorted(ours.items(), key=lambda kv: kv[1].sort_order):
        if not room.is_published:
            continue
        offer = offers.get(slug)
        selling = offer.price_per_night if offer and offer.price_per_night else None
        rows.append(
            {
                "roomSlug": slug,
                "roomName": room.short_name or room.name,
                "sitePrice": room.price,
                "sellingFrom": selling,
                "rateName": offer.rates[0].name if offer and offer.rates else "",
                "difference": (room.price - selling) if selling else None,
                "onSale": bool(offer and offer.rooms_left),
            }
        )

    return {
        "checkedOn": check_in.isoformat(),
        "reachable": reachable,
        "rooms": rows,
        "mismatched": sum(1 for r in rows if r["difference"]),
    }

@router.post("/prices/sync")
async def sync_prices(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    """
    Подтянуть цены сайта из Exely одним нажатием.

    Раньше цену меняли в двух не связанных местах, и она расходилась молча.
    Здесь — механический перенос: то же число, что показывает панель
    сравнения, записывается в цену номера на сайте.

    Не автоматический процесс по расписанию, а кнопка. Тарифы Exely сейчас
    перенастраивают, и постоянный автосинк затащил бы на сайт сегодняшний
    беспорядок из чужого кабинета. Пока это осознанное действие: нажимают,
    когда сами видят, что цены в Exely устоялись.

    Категории, для которых система не назвала надёжную цену на выбранную
    дату, не трогаем — лучше оставить прежнее число, чем затереть его пустым
    результатом одного запроса.
    """
    rooms = {room.slug: room for room in (await session.execute(select(Room))).scalars().all()}
    exely = ExelyBookingSystem(room_names=await _room_names(session))

    check_in = hotel_today() + timedelta(days=7)
    try:
        live = await exely.availability(check_in, check_in + timedelta(days=1))
    except BookingSystemUnavailable as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Exely не ответил: {error}") from error

    offers = {o.room_slug: o for o in live.offers}
    changed = []
    for slug, room in rooms.items():
        if not room.is_published:
            continue
        offer = offers.get(slug)
        selling = offer.price_per_night if offer and offer.price_per_night else None
        if not selling or selling == room.price:
            continue
        changed.append(
            {
                "roomSlug": slug,
                "roomName": room.short_name or room.name,
                "before": room.price,
                "after": selling,
            }
        )
        room.price = selling

    if changed:
        await session.commit()

    return {"checkedOn": check_in.isoformat(), "changed": changed}
