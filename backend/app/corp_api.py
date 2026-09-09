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
from .almaty import today as hotel_today
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


async def live_availability(
    settings: Settings, check_in: date, check_out: date,
    want: list[tuple[str, str, int]],
) -> tuple[str, str]:
    """Хватает ли номеров на эти даты. Возвращает (вердикт, причина).

    Вердикты:
      ok       — всех запрошенных категорий хватает, можно подтверждать;
      short    — чего-то не хватает, и мы точно это знаем;
      unknown  — спросить не удалось; решает человек.

    Разделение «short» и «unknown» здесь главное. Отказать по ошибке — значит
    прогнать партнёра, которому номер был; подтвердить по ошибке — значит
    пообещать номер, которого нет. Оба исхода плохие, поэтому там, где мы не
    знаем, не делаем ни того, ни другого.

    Спрашиваем наличие НА ОДНОГО гостя, хотя в заявке их больше. Exely
    показывает лишь те категории, куда помещается запрошенное число людей, и
    на двоих одноместный не покажет вовсе — заявка на Standart Single
    получила бы отказ при свободном номере. Запрос на одного даёт самый
    широкий список, а вместимость мы и так проверяем отдельно.
    """
    from .booking_system import get_booking_system

    try:
        booking = get_booking_system(settings)
    except Exception as error:  # noqa: BLE001
        return "unknown", f"система бронирования не настроена: {error}"
    if booking is None:
        return "unknown", "система бронирования не настроена"

    try:
        result = await booking.availability(check_in, check_out, guests=1)
    except Exception as error:  # noqa: BLE001
        logger.warning("Наличие для авто-подтверждения не прочиталось: %s", error)
        return "unknown", "система бронирования не ответила"

    свободно = {offer.room_slug: offer.rooms_left for offer in result.offers}
    for slug, название, сколько in want:
        осталось = свободно.get(slug)
        if осталось is None:
            # Категория есть у нас, но неизвестна системе бронирования.
            # Сказать про неё нечего — пусть смотрит менеджер.
            return "unknown", f"категории «{название}» нет в системе бронирования"
        if осталось < сколько:
            return "short", f"{название}: свободно {осталось}, а в заявке {сколько}"
    return "ok", ""


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


ПИТАНИЕ = {"breakfast": "завтрак", "none": "без питания",
           "halfboard": "полупансион", "fullboard": "полный пансион"}


def exely_block(booking: CorpBooking, items: list[CorpBookingItem],
                company_name: str = "") -> str:
    """Всё, что нужно набрать в Exely, одним куском для копирования.

    Единственный шаг, который нельзя автоматизировать: Exely не создаёт
    брони извне. Раз человек всё равно перепечатывает данные, пусть он
    перепечатывает их из одного места, а не собирает по экрану — там, где
    собирают глазами, путают даты и фамилии.

    Формат один и тот же в админке и в сообщении WhatsApp: расходись они,
    человек начал бы сверять два источника вместо того, чтобы копировать.
    """
    строки = [
        f"{booking.check_in:%d.%m.%Y} → {booking.check_out:%d.%m.%Y}"
        f"  ({booking.nights} ноч.)",
    ]
    for item in items:
        строки.append(f"{item.room_name} × {item.rooms_count}")
    гости = f"{booking.adults} взр."
    if booking.children:
        гости += f", {booking.children} дет."
    строки.append(гости)
    кто = booking.guest_name or "имя не указано"
    if booking.guest_phone:
        кто += f", {booking.guest_phone}"
    строки.append(f"Гость: {кто}")
    строки.append(f"Питание: {ПИТАНИЕ.get(booking.meal_plan, booking.meal_plan)}")
    подпись = " · ".join(x for x in (company_name, booking.number) if x)
    строки.append(f"Оплата по счёту · {подпись}")
    if booking.comment:
        строки.append(f"Комментарий: {booking.comment}")
    return "\n".join(строки)


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

    company_ids = {b.company_id for b in bookings}
    companies: dict[int, Company] = {}
    if company_ids:
        companies_result = await session.execute(
            select(Company).where(Company.id.in_(company_ids))
        )
        companies = {c.id: c for c in companies_result.scalars().all()}

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
        company = companies.get(booking.company_id)
        if company:
            model.companySlug = company.slug
            model.companyName = company.name
        model.exelyBlock = exely_block(
            booking, by_booking.get(booking.id, []),
            company.name if company else "")
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
    settings: Settings = Depends(get_settings),
):
    """
    Оформление брони по корпоративным ценам.

    Обычной компании бронь создаётся заявкой в статусе `new`: наличие
    подтверждает менеджер. Обещать гостю подтверждённый номер, не умея его
    подтвердить, нельзя, и в кабинете это честно подписано как заявка.

    Доверенному партнёру (`company.auto_confirm`) заявка подтверждается сама,
    если система бронирования говорит, что номера свободны. Что это значит и
    чего НЕ значит:

    **Значит:** на момент проверки в Exely были свободные номера нужных
    категорий, и партнёр получает ответ за секунду вместо часа ожидания.

    **Не значит:** бронь занесена в шахматку. Exely не создаёт брони через
    API вовсе — только отдаёт наличие. Занести её обязан человек, и
    уведомление отелю об этом говорит прямо.

    Отказ отправляется сразу и с точной причиной — это лучше тишины, в
    которую партнёр упирается, когда менеджер не успевает ответить.
    """
    if hotel_today() > data.checkIn:
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

    # Завтрак входит в цену любого номера, поэтому отказ — это вычет, а не
    # доплата. Сколько снимать, записано в договоре компании; ноль означает
    # «цена та же», и тогда выбор просто сохраняется для кухни.
    #
    # Вычет не может увести сумму в минус: если в договоре завтрак дороже
    # ночи, виновата настройка, а отрицательный счёт компании — уже наша
    # ошибка.
    if data.mealPlan == "none" and company.breakfast_price:
        total = max(0, total - company.breakfast_price * guests * nights)

    if guests > capacity:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Выбранные номера вмещают {capacity} гостей, а в заявке {guests}",
        )

    # Доверенный партнёр: подтверждаем сами, если номера действительно есть.
    статус = "new"
    сам_подтвердил = False
    if company.auto_confirm:
        вердикт, причина = await live_availability(
            settings, data.checkIn, data.checkOut,
            [(item.room_slug, item.room_name, item.rooms_count) for item in items],
        )
        if вердикт == "ok":
            статус, сам_подтвердил = "confirmed", True
        elif вердикт == "short":
            # Отказ сразу и с цифрами. Партнёр переиграет даты в ту же минуту,
            # а не через час, когда менеджер дойдёт до почты.
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Свободных номеров не хватает. {причина}"
            )
        else:
            # Спросить не вышло — решает человек, как и раньше. Молча
            # подтвердить здесь значило бы пообещать номер наугад.
            logger.info("Заявка %s ушла менеджеру: %s", user.company_id, причина)

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
        meal_plan=data.mealPlan,
        status=статус,
        auto_confirmed=сам_подтвердил,
        confirmed_at=utcnow() if сам_подтвердил else None,
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
        breakfast_price=data.breakfastPrice,
        auto_confirm=data.autoConfirm,
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
        "breakfastPrice": "breakfast_price",
        "isActive": "is_active",
        "autoConfirm": "auto_confirm",
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


@admin.post("/bookings/{booking_id}/entered", response_model=CorpBookingOut)
async def admin_mark_entered(
    booking_id: int,
    data: CorpBookingEnteredIn,
    session: AsyncSession = Depends(get_session),
):
    """Отметить, что бронь занесена в шахматку Exely.

    Отдельная отметка, а не статус. Статус описывает сделку с компанией
    (подтверждена, выставлен счёт, оплачена), а занесение — работу отеля
    внутри Exely: у подтверждённой брони может быть выставлен счёт, а в
    шахматке её всё ещё нет. Смешав их, мы потеряли бы ровно тот случай,
    ради которого отметка и нужна.

    Снять отметку тоже можно: занесли не ту бронь — надо иметь возможность
    вернуть её в очередь, а не заводить вторую.
    """
    booking = await session.get(CorpBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Бронирование не найдено")

    booking.entered_at = utcnow() if data.entered else None
    await session.commit()
    await session.refresh(booking)
    return (await _bookings_out(session, [booking]))[0]
