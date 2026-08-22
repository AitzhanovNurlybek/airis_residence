"""
Корпоративный кабинет: то, чем пользуется компания, и то, чем ею управляет отель.

Два роутера в одном файле, потому что это одна предметная область и одни и те
же правила расчёта цены. Кто что видит, разделено зависимостями: `corp` пускает
сотрудника компании (corp_auth), `admin` — администратора отеля (auth).

Про связи между таблицами. Ни у одной модели нет `relationship`, и это
намеренно: в асинхронном SQLAlchemy обращение к незагруженной связи падает уже
во время сериализации ответа, далеко от места, где её забыли подгрузить.
Здесь всё читается явными запросами — многословнее, зато предсказуемо.
"""

import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_admin
from .config import Settings, get_settings
from .corp_auth import (
    create_token,
    hash_password,
    require_corp_admin,
    require_corp_user,
    verify_password,
)
from .db import (
    Company,
    CompanyRate,
    CompanyUser,
    CorpBooking,
    CorpBookingItem,
    Room,
    get_session,
    utcnow,
)
from .notify import notify_corp_booking
from .throttle import PER_OFFICE_IP, client_ip, reset, too_many
from .schemas import (
    CompanyIn,
    CompanyOut,
    CompanyPatch,
    CompanyRateIn,
    CompanyRateOut,
    CompanyUserIn,
    CompanyUserOut,
    CompanyUserPatch,
    CorpBookingIn,
    CorpBookingItemOut,
    CorpBookingOut,
    CorpBookingStatusIn,
    CorpCancelIn,
    CorpLoginIn,
    CorpLoginOut,
    CorpMeOut,
    CorpPasswordIn,
    CorpRoomOut,
)

logger = logging.getLogger(__name__)

corp = APIRouter(prefix="/api/corp", tags=["корпоративный кабинет"])
admin = APIRouter(
    prefix="/api/admin/corp",
    tags=["admin: компании"],
    dependencies=[Depends(require_admin)],
)

#: Брони, которые считаются действующими: они висят на компании и попадают
#: в счётчик на первом экране. Отменённая и оплаченная — уже история.
ACTIVE_STATUSES = ("new", "confirmed", "invoiced")


# ─────────────────────────────── Цены ─────────────────────────────────


def corp_price(public_price: int, discount_percent: int, override: int | None) -> int:
    """
    Корпоративная цена номера.

    Точная цена из договора (override) важнее процента: если по конкретной
    категории договорились на 26 500, никакая скидка от стойки этого не
    отменяет. Процент — удобный случай «минус N % на весь прайс».

    Результат округляется вниз до сотни тенге. Прайс отеля круглый, и
    «26 437 ₸» в счёте выглядит как ошибка расчёта, а не как скидка.
    """
    if override is not None:
        return max(0, override)
    if discount_percent > 0:
        discounted = public_price * (100 - discount_percent) // 100
        return max(0, discounted // 100 * 100)
    return public_price


async def _rates_map(session: AsyncSession, company_id: int) -> dict[str, int]:
    result = await session.execute(
        select(CompanyRate).where(CompanyRate.company_id == company_id)
    )
    return {rate.room_slug: rate.price for rate in result.scalars().all()}


async def _published_rooms(session: AsyncSession) -> list[Room]:
    result = await session.execute(
        select(Room).where(Room.is_published.is_(True)).order_by(Room.sort_order, Room.id)
    )
    return list(result.scalars().all())


# ────────────────────────── Сборка ответов ────────────────────────────


async def _bookings_out(
    session: AsyncSession, bookings: list[CorpBooking]
) -> list[CorpBookingOut]:
    """
    Достраивает брони строками и именами сотрудников.

    Два запроса на весь список, а не по два на каждую бронь: за год у активной
    компании их накопятся сотни, и запрос в цикле превратит страницу истории
    в минуту ожидания.
    """
    if not bookings:
        return []

    ids = [booking.id for booking in bookings]
    items_result = await session.execute(
        select(CorpBookingItem).where(CorpBookingItem.booking_id.in_(ids))
    )
    by_booking: dict[int, list[CorpBookingItem]] = {}
    for item in items_result.scalars().all():
        by_booking.setdefault(item.booking_id, []).append(item)

    author_ids = {b.created_by_id for b in bookings if b.created_by_id}
    names: dict[int, str] = {}
    if author_ids:
        users_result = await session.execute(
            select(CompanyUser).where(CompanyUser.id.in_(author_ids))
        )
        for user in users_result.scalars().all():
            names[user.id] = user.full_name or user.email

    out: list[CorpBookingOut] = []
    for booking in bookings:
        model = CorpBookingOut.model_validate(booking)
        model.items = [
            CorpBookingItemOut.model_validate(item)
            for item in by_booking.get(booking.id, [])
        ]
        model.createdByName = names.get(booking.created_by_id or 0, "")
        out.append(model)
    return out


# ═══════════════════════ Кабинет компании ════════════════════════════


@corp.post("/login", response_model=CorpLoginOut)
async def corp_login(
    data: CorpLoginIn,
    request: Request,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    """
    Вход сотрудника.

    Ответ на неверную почту и на неверный пароль одинаковый: иначе форму
    входа можно использовать как справочник «эта компания у вас обслуживается».

    Перебор тормозится по двум ключам сразу, и пределы у них разные. По почте
    жёстко: подбирают всегда конкретную учётку. По адресу щедро — сотрудники
    компании сидят за общим офисным NAT, и общий лимит на всех заперал бы
    контору после пары опечаток у двух человек.
    """
    email = data.email.strip().lower()

    ip_key = f"corp-ip:{client_ip(request)}"
    user_key = f"corp-user:{email}"
    # Порядок важен: обе попытки должны быть отмечены, поэтому сначала считаем,
    # а потом решаем. `or` с ранним выходом пропустил бы вторую.
    over_ip = too_many(ip_key, PER_OFFICE_IP)
    over_user = too_many(user_key)
    if over_ip or over_user:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Слишком много попыток, подождите 5 минут"
        )

    result = await session.execute(select(CompanyUser).where(CompanyUser.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверная почта или пароль")

    company = await session.get(Company, user.company_id)
    if company is None or not company.is_active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Доступ компании приостановлен — свяжитесь с менеджером Airis",
        )

    reset(ip_key)
    reset(user_key)

    token, expires_at = create_token(settings, user)
    user.last_login_at = utcnow()
    await session.commit()

    return CorpLoginOut(
        token=token,
        expires_at=expires_at,
        role=user.role,
        company_name=company.name,
    )


@corp.get("/me", response_model=CorpMeOut)
async def corp_me(
    user: CompanyUser = Depends(require_corp_user),
    session: AsyncSession = Depends(get_session),
):
    """Первый экран кабинета: карточка компании и три счётчика."""
    company = await session.get(Company, user.company_id)

    # Считаем в базе, а не в питоне. Раньше сюда тянулись ВСЕ брони компании
    # целиком со всеми полями — ради трёх чисел на первом экране. У активного
    # клиента их за год накапливаются сотни, и каждая загрузка кабинета
    # везла их через полмира: база в Сиднее, приложение в Вашингтоне.
    totals = await session.execute(
        select(
            CorpBooking.status,
            func.count(CorpBooking.id),
            func.coalesce(func.sum(CorpBooking.total_amount), 0),
        )
        .where(CorpBooking.company_id == user.company_id)
        .group_by(CorpBooking.status)
    )

    active_count = 0
    active_sum = 0
    paid_sum = 0
    for status_value, count, amount in totals.all():
        if status_value in ACTIVE_STATUSES:
            active_count += count
            active_sum += amount
        elif status_value == "paid":
            paid_sum += amount

    user_out = CompanyUserOut.model_validate(user)
    user_out.hasPassword = bool(user.password_hash)

    return CorpMeOut(
        user=user_out,
        company=CompanyOut.model_validate(company),
        activeBookings=active_count,
        totalAmount=active_sum,
        paidAmount=paid_sum,
    )


@corp.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def corp_change_password(
    data: CorpPasswordIn,
    user: CompanyUser = Depends(require_corp_user),
    session: AsyncSession = Depends(get_session),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Текущий пароль не подходит")
    user.password_hash = hash_password(data.new_password)
    await session.commit()


@corp.get("/rooms", response_model=list[CorpRoomOut])
async def corp_rooms(
    user: CompanyUser = Depends(require_corp_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Номера с ценами этой компании.

    Публичная цена отдаётся рядом с корпоративной специально: сотрудник должен
    видеть, что бронирование через кабинет действительно дешевле сайта, —
    иначе он пойдёт бронировать на агрегаторе.
    """
    company = await session.get(Company, user.company_id)
    rates = await _rates_map(session, user.company_id)
    rooms = await _published_rooms(session)

    return [
        CorpRoomOut(
            slug=room.slug,
            name=room.name,
            shortName=room.short_name,
            area=room.area,
            capacity=room.capacity,
            beds=room.beds,
            summary=room.summary,
            features=list(room.features or []),
            images=list(room.images or []),
            publicPrice=room.price,
            corpPrice=corp_price(room.price, company.discount_percent, rates.get(room.slug)),
        )
        for room in rooms
    ]


@corp.get("/bookings", response_model=list[CorpBookingOut])
async def corp_bookings(
    user: CompanyUser = Depends(require_corp_user),
    session: AsyncSession = Depends(get_session),
):
    """
    История броней.

    Ответственный видит все брони компании — ему за них платить. Обычный
    сотрудник только свои: командировки коллег его не касаются.
    """
    query = select(CorpBooking).where(CorpBooking.company_id == user.company_id)
    if user.role != "admin":
        query = query.where(CorpBooking.created_by_id == user.id)
    query = query.order_by(CorpBooking.created_at.desc())

    result = await session.execute(query)
    return await _bookings_out(session, list(result.scalars().all()))


@corp.post("/bookings", response_model=CorpBookingOut, status_code=status.HTTP_201_CREATED)
async def corp_create_booking(
    data: CorpBookingIn,
    background: BackgroundTasks,
    user: CompanyUser = Depends(require_corp_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Оформление брони по корпоративным ценам.

    Пока система бронирования отеля не отдаёт API, наличие номеров здесь не
    проверяется — подтверждает менеджер. Поэтому бронь создаётся в статусе
    `new` и в кабинете честно подписана как заявка: обещать гостю
    подтверждённый номер, не умея его подтвердить, нельзя.
    """
    if date.today() > data.checkIn:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Дата заезда уже прошла")

    company = await session.get(Company, user.company_id)
    rates = await _rates_map(session, user.company_id)
    rooms = {room.slug: room for room in await _published_rooms(session)}

    nights = (data.checkOut - data.checkIn).days
    items: list[CorpBookingItem] = []
    capacity = 0
    total = 0

    for line in data.items:
        room = rooms.get(line.roomSlug)
        if room is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Номер «{line.roomSlug}» недоступен"
            )
        price = corp_price(room.price, company.discount_percent, rates.get(room.slug))
        amount = price * line.roomsCount * nights
        capacity += room.capacity * line.roomsCount
        total += amount
        items.append(
            CorpBookingItem(
                room_slug=room.slug,
                room_name=room.short_name or room.name,
                rooms_count=line.roomsCount,
                price_per_night=price,
                amount=amount,
            )
        )

    guests = data.adults + data.children
    if guests > capacity:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Выбранные номера вмещают {capacity} гостей, а в заявке {guests}",
        )

    booking = CorpBooking(
        number="",
        company_id=user.company_id,
        created_by_id=user.id,
        check_in=data.checkIn,
        check_out=data.checkOut,
        nights=nights,
        adults=data.adults,
        children=data.children,
        guest_name=data.guestName.strip(),
        guest_phone=data.guestPhone.strip(),
        comment=data.comment.strip(),
        status="new",
        total_amount=total,
    )
    session.add(booking)
    # Номер брони строится из id, а id выдаёт база. flush получает его, не
    # закрывая транзакцию: если дальше что-то упадёт, не останется брони с
    # пустым номером.
    await session.flush()
    booking.number = f"K-{booking.id:04d}"

    for item in items:
        item.booking_id = booking.id
        session.add(item)

    await session.commit()
    await session.refresh(booking)

    # Уведомление — вспомогательный канал: заявка уже в базе и видна менеджеру
    # в админке, поэтому молчание Telegram ничего не теряет. Это не тот случай,
    # когда ошибку канала можно глушить: тут её просто нечего терять.
    background.add_task(notify_corp_booking, booking.id)

    return (await _bookings_out(session, [booking]))[0]


@corp.post("/bookings/{booking_id}/cancel", response_model=CorpBookingOut)
async def corp_cancel_booking(
    booking_id: int,
    data: CorpCancelIn,
    user: CompanyUser = Depends(require_corp_user),
    session: AsyncSession = Depends(get_session),
):
    booking = await session.get(CorpBooking, booking_id)
    # Проверка компании обязательна: без неё чужую бронь можно было бы
    # отменить, просто подставив другой id в адрес.
    if booking is None or booking.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Бронирование не найдено")
    if user.role != "admin" and booking.created_by_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это бронирование оформил другой сотрудник")

    if booking.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "Бронирование уже отменено")
    if booking.status == "paid":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Оплаченное бронирование отменяет менеджер — напишите ему",
        )

    booking.status = "cancelled"
    booking.cancelled_at = utcnow()
    booking.cancel_reason = data.reason.strip()
    await session.commit()
    await session.refresh(booking)
    return (await _bookings_out(session, [booking]))[0]


# ─────────────────── Сотрудники (ответственный компании) ──────────────


@corp.get("/employees", response_model=list[CompanyUserOut])
async def corp_employees(
    user: CompanyUser = Depends(require_corp_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CompanyUser)
        .where(CompanyUser.company_id == user.company_id)
        .order_by(CompanyUser.id)
    )
    out = []
    for item in result.scalars().all():
        model = CompanyUserOut.model_validate(item)
        model.hasPassword = bool(item.password_hash)
        out.append(model)
    return out


@corp.post("/employees", response_model=CompanyUserOut, status_code=status.HTTP_201_CREATED)
async def corp_add_employee(
    data: CompanyUserIn,
    user: CompanyUser = Depends(require_corp_admin),
    session: AsyncSession = Depends(get_session),
):
    return await _create_user(session, user.company_id, data)


@corp.patch("/employees/{user_id}", response_model=CompanyUserOut)
async def corp_edit_employee(
    user_id: int,
    data: CompanyUserPatch,
    user: CompanyUser = Depends(require_corp_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await session.get(CompanyUser, user_id)
    if target is None or target.company_id != user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сотрудник не найден")
    # Отключить самого себя — это запереть компанию снаружи: последний
    # ответственный уйдёт, и заводить сотрудников станет некому.
    if target.id == user.id and data.isActive is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя отключить собственный доступ")
    result = _apply_user_patch(target, data)
    await session.commit()
    return result


# ═══════════════════ Управление со стороны отеля ═════════════════════


async def _company_by_slug(session: AsyncSession, slug: str) -> Company:
    result = await session.execute(select(Company).where(Company.slug == slug))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Компания не найдена")
    return company


async def _create_user(
    session: AsyncSession, company_id: int, data: CompanyUserIn
) -> CompanyUserOut:
    email = data.email.strip().lower()
    exists = await session.execute(select(CompanyUser).where(CompanyUser.email == email))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такая почта уже заведена")

    user = CompanyUser(
        company_id=company_id,
        email=email,
        full_name=data.fullName.strip(),
        phone=data.phone.strip(),
        role=data.role,
        # Пароль можно не задавать сразу: пока его нет, войти нельзя —
        # verify_password на пустом хеше всегда отвечает «нет».
        password_hash=hash_password(data.password) if data.password else "",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    out = CompanyUserOut.model_validate(user)
    out.hasPassword = bool(user.password_hash)
    return out


def _apply_user_patch(user: CompanyUser, data: CompanyUserPatch) -> CompanyUserOut:
    if data.fullName is not None:
        user.full_name = data.fullName.strip()
    if data.phone is not None:
        user.phone = data.phone.strip()
    if data.role is not None:
        user.role = data.role
    if data.isActive is not None:
        user.is_active = data.isActive
    if data.password:
        user.password_hash = hash_password(data.password)

    out = CompanyUserOut.model_validate(user)
    out.hasPassword = bool(user.password_hash)
    return out


@admin.get("/companies", response_model=list[CompanyOut])
async def admin_companies(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Company).order_by(Company.name))
    return list(result.scalars().all())


@admin.post("/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def admin_create_company(
    data: CompanyIn, session: AsyncSession = Depends(get_session)
):
    exists = await session.execute(select(Company).where(Company.slug == data.slug))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой код компании уже занят")

    company = Company(
        slug=data.slug,
        name=data.name.strip(),
        bin=data.bin.strip(),
        contract_number=data.contractNumber.strip(),
        contract_date=data.contractDate,
        payment_terms=data.paymentTerms.strip(),
        manager_name=data.managerName.strip(),
        manager_email=data.managerEmail.strip(),
        manager_phone=data.managerPhone.strip(),
        discount_percent=data.discountPercent,
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


@admin.patch("/companies/{slug}", response_model=CompanyOut)
async def admin_edit_company(
    slug: str, data: CompanyPatch, session: AsyncSession = Depends(get_session)
):
    company = await _company_by_slug(session, slug)
    fields = {
        "name": "name",
        "bin": "bin",
        "contractNumber": "contract_number",
        "contractDate": "contract_date",
        "paymentTerms": "payment_terms",
        "managerName": "manager_name",
        "managerEmail": "manager_email",
        "managerPhone": "manager_phone",
        "discountPercent": "discount_percent",
        "isActive": "is_active",
    }
    for incoming, column in fields.items():
        value = getattr(data, incoming)
        if value is not None:
            setattr(company, column, value.strip() if isinstance(value, str) else value)
    await session.commit()
    await session.refresh(company)
    return company


@admin.delete("/companies/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_company(
    slug: str,
    force: bool = False,
    session: AsyncSession = Depends(get_session),
):
    """
    Удаление компании вместе с сотрудниками, прайсом и историей броней.

    Компанию без единой брони удаляем сразу: такие заводят по ошибке, и
    заставлять человека подтверждать удаление пустышки — только раздражать.

    Компанию с историей — только при `force`. Брони это не просто строки: у
    них номера счетов, суммы и даты, то есть бухгалтерский след. Отель обязан
    узнать, сколько записей исчезнет, ДО того как они исчезнут, а не после.
    Если компания просто перестала обслуживаться, правильный ход — не удалять,
    а приостановить доступ: кабинет закроется, а история останется.

    Связанное удаляем явными запросами, а не каскадом базы. Каскад объявлен в
    схеме, но SQLite по умолчанию внешние ключи не проверяет, а Postgres
    проверяет: локально бы осталось висеть сиротами то, что на боевом удалилось
    бы. Одинаковое поведение важнее краткости.
    """
    company = await _company_by_slug(session, slug)

    bookings_result = await session.execute(
        select(CorpBooking.id).where(CorpBooking.company_id == company.id)
    )
    booking_ids = [row[0] for row in bookings_result.all()]

    if booking_ids and not force:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"У компании {len(booking_ids)} бронирований — вместе с ней исчезнет "
            f"вся история и номера счетов. Если компания просто больше не "
            f"обслуживается, приостановите доступ вместо удаления.",
        )

    if booking_ids:
        await session.execute(
            delete(CorpBookingItem).where(CorpBookingItem.booking_id.in_(booking_ids))
        )
        await session.execute(delete(CorpBooking).where(CorpBooking.id.in_(booking_ids)))

    await session.execute(delete(CompanyRate).where(CompanyRate.company_id == company.id))
    await session.execute(delete(CompanyUser).where(CompanyUser.company_id == company.id))
    await session.delete(company)
    await session.commit()

    logger.info(
        "Удалена компания %s: сотрудников и прайс снесли, броней — %s",
        slug,
        len(booking_ids),
    )


@admin.get("/companies/{slug}/users", response_model=list[CompanyUserOut])
async def admin_company_users(slug: str, session: AsyncSession = Depends(get_session)):
    company = await _company_by_slug(session, slug)
    result = await session.execute(
        select(CompanyUser).where(CompanyUser.company_id == company.id).order_by(CompanyUser.id)
    )
    out = []
    for item in result.scalars().all():
        model = CompanyUserOut.model_validate(item)
        model.hasPassword = bool(item.password_hash)
        out.append(model)
    return out


@admin.post(
    "/companies/{slug}/users",
    response_model=CompanyUserOut,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_user(
    slug: str, data: CompanyUserIn, session: AsyncSession = Depends(get_session)
):
    company = await _company_by_slug(session, slug)
    return await _create_user(session, company.id, data)


@admin.patch("/users/{user_id}", response_model=CompanyUserOut)
async def admin_edit_user(
    user_id: int, data: CompanyUserPatch, session: AsyncSession = Depends(get_session)
):
    user = await session.get(CompanyUser, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сотрудник не найден")
    result = _apply_user_patch(user, data)
    await session.commit()
    return result


@admin.get("/companies/{slug}/rates", response_model=list[CompanyRateOut])
async def admin_company_rates(slug: str, session: AsyncSession = Depends(get_session)):
    company = await _company_by_slug(session, slug)
    result = await session.execute(
        select(CompanyRate).where(CompanyRate.company_id == company.id)
    )
    return list(result.scalars().all())


@admin.put("/companies/{slug}/rates", response_model=list[CompanyRateOut])
async def admin_set_rates(
    slug: str, data: list[CompanyRateIn], session: AsyncSession = Depends(get_session)
):
    """
    Прайс компании целиком: что прислали — то и остаётся.

    Замена списком, а не по одной строке, потому что цены правят пачкой при
    перезаключении договора, и «сохранил три из пяти» — это хуже, чем ошибка.
    """
    company = await _company_by_slug(session, slug)
    known = {room.slug for room in await _published_rooms(session)}

    existing_result = await session.execute(
        select(CompanyRate).where(CompanyRate.company_id == company.id)
    )
    existing = {rate.room_slug: rate for rate in existing_result.scalars().all()}

    incoming: dict[str, int] = {}
    for line in data:
        if line.roomSlug not in known:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Номера «{line.roomSlug}» нет в прайсе"
            )
        incoming[line.roomSlug] = line.price

    for slug_key, price in incoming.items():
        if slug_key in existing:
            existing[slug_key].price = price
        else:
            session.add(
                CompanyRate(company_id=company.id, room_slug=slug_key, price=price)
            )
    for slug_key, rate in existing.items():
        if slug_key not in incoming:
            await session.delete(rate)

    await session.commit()
    result = await session.execute(
        select(CompanyRate).where(CompanyRate.company_id == company.id)
    )
    return list(result.scalars().all())


@admin.get("/bookings", response_model=list[CorpBookingOut])
async def admin_bookings(
    company: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(CorpBooking)
    if company:
        found = await _company_by_slug(session, company)
        query = query.where(CorpBooking.company_id == found.id)
    query = query.order_by(CorpBooking.created_at.desc())
    result = await session.execute(query)
    return await _bookings_out(session, list(result.scalars().all()))


@admin.patch("/bookings/{booking_id}/status", response_model=CorpBookingOut)
async def admin_set_booking_status(
    booking_id: int,
    data: CorpBookingStatusIn,
    session: AsyncSession = Depends(get_session),
):
    """Менеджер отеля ведёт заявку по статусам: подтвердил, выставил счёт, оплачено."""
    booking = await session.get(CorpBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Бронирование не найдено")

    booking.status = data.status
    if data.status == "confirmed" and booking.confirmed_at is None:
        booking.confirmed_at = utcnow()
    if data.status == "cancelled":
        booking.cancelled_at = utcnow()
        booking.cancel_reason = data.reason.strip()
    if data.invoiceNumber:
        booking.invoice_number = data.invoiceNumber.strip()

    await session.commit()
    await session.refresh(booking)
    return (await _bookings_out(session, [booking]))[0]
