"""
Локальная шахматка — учебная копия того, чем заведует Exely.

Заглушка на хеше умела только показывать выдуманную занятость. Этого хватало,
чтобы консьерж рассказал про наличие, но не хватало, чтобы проверить главное:
как он обращается с бронями, когда их можно создавать, менять и отменять.
Ошибка в чтении стоит неверного ответа, ошибка в записи — потерянной брони.

Поэтому здесь настоящая таблица в нашей базе. Свободные номера считаются из
неё же: сколько всего минус сколько занято на худшую ночь периода. Всё, что
консьерж делает в разговоре, видно в базе, и наоборот — правка в базе сразу
меняет его ответы.

Когда придёт доступ к Exely, этот файл заменится адаптером к чужому API, а
вызывающий код останется прежним: набор операций подобран по тому, что умеет
любая шахматка, а не по тому, что удобно нам.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db import LocalBooking, LocalPayment, LocalStock, utcnow
from .base import Availability, ExternalBooking, ExternalInvoice, RoomOffer
from ..almaty import today as hotel_today

#: Разбивка номерного фонда по категориям — для учебной шахматки.
#:
#: Числа сняты с настоящей шахматки Exely 2026-08-24, по номерам комнат:
#:   Standart Single — 106, 207
#:   Standart        — 102, 203, 205, 206, 208–212, 303, 305–312
#:   Standart Twin   — 103, 202, 302
#:   Comfort         — 201, 204, 213, 301 (список был обрезан экраном)
#: Всего в отеле 34 номера; на Comfort+, Apart и возможный остаток Comfort
#: приходится семь, разложены оценочно.
#:
#: До этого здесь стояли выдуманные цифры, и ошибались они заметно: у Standart
#: было 12 вместо 18, у Single — 6 вместо 2. Учебная шахматка врала не только
#: занятостью, но и самим размером отеля.
#:
#: Настоящий источник — Exely. Эта таблица уходит целиком, когда подключим её
#: API: там номерной фонд отдаётся вместе с наличием.
DEFAULT_STOCK: dict[str, int] = {
    "standart-single": 2,
    "standart": 18,
    "standart-twin": 3,
    "comfort": 4,
    # Ниже — оценка: этих строк на снимке шахматки не было видно.
    "comfort-plus": 4,
    "apart": 3,
}


class NotEnoughRooms(RuntimeError):
    """Свободных номеров меньше, чем просят."""


class BookingNotFound(RuntimeError):
    """Брони с таким номером нет."""


def _nights(check_in: date, check_out: date) -> list[date]:
    return [check_in + timedelta(days=i) for i in range((check_out - check_in).days)]


class LocalBookingSystem:
    """Шахматка в нашей базе: читает, пишет, отменяет."""

    name = "Локальная шахматка"

    #: Здесь поиск по телефону работает, поэтому выдавать бронь по одному
    #: только номеру нельзя: номера короткие (L-0007), их легко угадать.
    finds_by_phone = True
    source = "stub"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        room_names: dict[str, str] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._names = room_names or {}

    def display(self, slug: str) -> str:
        return self._names.get(slug, slug)

    # ─────────────────────────── чтение ────────────────────────────

    async def _stock(self, session: AsyncSession) -> dict[str, int]:
        """
        Сколько номеров каждой категории есть в отеле.

        Категории берутся от номеров сайта (`self._names`), а не из жёсткого
        списка. Иначе шахматка отставала бы от отеля: когда номер «Luxe»
        переименовали в «Comfort Plus», здесь осталась бы категория, которой
        на сайте уже нет, а новой не появилось бы вовсе.

        DEFAULT_STOCK остаётся подсказкой для количества — сколько комнат
        каждого типа. Настоящее число знает Exely; до него это цифра, которую
        владелец правит руками.
        """
        rows = (await session.execute(select(LocalStock))).scalars().all()
        known = {row.room_slug: row.rooms_total for row in rows}

        # Что считаем категориями отеля: номера сайта плюс всё, что уже
        # заведено в фонде песочницы. Второе нужно ради Apart — Exely его
        # продаёт, страницы на сайте нет, а проверять поведение на нём надо.
        wanted = (set(self._names) | set(known)) or set(DEFAULT_STOCK)
        missing = wanted - set(known)
        for slug in sorted(missing):
            session.add(LocalStock(room_slug=slug, rooms_total=DEFAULT_STOCK.get(slug, 1)))
            known[slug] = DEFAULT_STOCK.get(slug, 1)
        if missing:
            await session.commit()

        # Категории, которых у отеля больше нет, из ответа убираем, но строки
        # не удаляем: на них могут висеть прошлые брони, и терять историю
        # из-за переименования нельзя.
        return {slug: total for slug, total in known.items() if slug in wanted}

    async def _busy(
        self, session: AsyncSession, check_in: date, check_out: date, *, skip_ref: str = ""
    ) -> dict[str, int]:
        """Сколько номеров каждой категории занято на худшую ночь периода."""
        query = select(LocalBooking).where(
            LocalBooking.status == "booked",
            LocalBooking.check_in < check_out,
            LocalBooking.check_out > check_in,
        )
        if skip_ref:
            # При переносе брони саму себя считать занятой нельзя: иначе
            # сдвинуть даты на один день будет невозможно в полном отеле.
            query = query.where(LocalBooking.ref != skip_ref)

        overlapping = (await session.execute(query)).scalars().all()

        worst: dict[str, int] = {}
        for night in _nights(check_in, check_out):
            per_night: dict[str, int] = {}
            for booking in overlapping:
                if booking.check_in <= night < booking.check_out:
                    per_night[booking.room_slug] = (
                        per_night.get(booking.room_slug, 0) + booking.rooms_count
                    )
            for slug, count in per_night.items():
                worst[slug] = max(worst.get(slug, 0), count)
        return worst

    async def ensure_stock(self) -> dict[str, int]:
        """
        Разложить номера по категориям, если это первый заход.

        Отдельный метод, потому что через availability получалось не всегда:
        на нулевом периоде тот выходит раньше, чем доберётся до раскладки, и
        страница шахматки открывалась с пустым списком категорий — читалось
        как «в отеле нет номеров».
        """
        async with self._sessions() as session:
            return await self._stock(session)

    async def availability(self, check_in: date, check_out: date) -> Availability:
        nights = (check_out - check_in).days
        if nights <= 0:
            return Availability(check_in, check_out, 0, [], "stub")

        async with self._sessions() as session:
            stock = await self._stock(session)
            busy = await self._busy(session, check_in, check_out)

        offers = [
            RoomOffer(
                room_slug=slug,
                room_name=self.display(slug),
                rooms_left=max(0, total - busy.get(slug, 0)),
                price_per_night=None,
                source="stub",
            )
            for slug, total in stock.items()
        ]
        return Availability(check_in, check_out, nights, offers, "stub")

    async def get_booking(self, external_id: str) -> ExternalBooking | None:
        async with self._sessions() as session:
            booking = await self._by_ref(session, external_id, strict=False)
            if booking is None:
                return None
            return self._to_external(booking)

    async def find_bookings(self, *, phone: str = "", name: str = "") -> list[ExternalBooking]:
        """Поиск брони, когда гость не помнит её номер."""
        query = select(LocalBooking).order_by(LocalBooking.check_in)
        digits = "".join(c for c in phone if c.isdigit())
        if digits:
            # Сравниваем по последним девяти цифрам: один и тот же номер гость
            # пишет то с +7, то с 8, то без кода вовсе.
            tail = digits[-9:]
            rows = await self._all(query)
            return [
                self._to_external(b)
                for b in rows
                if "".join(c for c in b.guest_phone if c.isdigit()).endswith(tail)
            ]
        if name.strip():
            needle = name.strip().casefold()
            rows = await self._all(query)
            return [self._to_external(b) for b in rows if needle in b.guest_name.casefold()]
        return []

    async def _all(self, query) -> list[LocalBooking]:
        async with self._sessions() as session:
            return list((await session.execute(query)).scalars().all())

    async def invoices(
        self, *, company_bin: str = "", external_id: str = ""
    ) -> list[ExternalInvoice]:
        if not external_id:
            return []
        async with self._sessions() as session:
            booking = await self._by_ref(session, external_id, strict=False)
            if booking is None or not booking.amount:
                return []
            return [
                ExternalInvoice(
                    number=booking.ref,
                    issued_at=booking.created_at.date(),
                    due_at=booking.check_in,
                    amount=booking.amount,
                    paid_amount=booking.paid_amount,
                    status="paid" if booking.paid_amount >= booking.amount else "unpaid",
                    source="stub",
                )
            ]

    # ─────────────────────────── запись ────────────────────────────

    async def create_booking(
        self,
        *,
        room_slug: str,
        rooms_count: int,
        check_in: date,
        check_out: date,
        guest_name: str = "",
        guest_phone: str = "",
        amount: int = 0,
        origin: str = "manual",
        note: str = "",
    ) -> ExternalBooking:
        if (check_out - check_in).days <= 0:
            raise ValueError("Дата выезда должна быть позже даты заезда")
        if rooms_count <= 0:
            raise ValueError("Номеров должно быть хотя бы один")
        # Заезд задним числом. Проверка стоит здесь, а не в правилах модели:
        # правило — просьба, а его достаточно уговорить. Гость, назвавший
        # прошлогоднюю дату, получил бы бронь, которую никто не заметит до
        # разбора шахматки.
        if check_in < hotel_today():
            raise ValueError(f"Дата заезда {check_in} уже прошла")

        async with self._sessions() as session:
            stock = await self._stock(session)
            if room_slug not in stock:
                raise ValueError(f"Такой категории нет: {room_slug}")

            busy = await self._busy(session, check_in, check_out)
            free = stock[room_slug] - busy.get(room_slug, 0)
            if free < rooms_count:
                raise NotEnoughRooms(
                    f"Свободно {max(0, free)} — запрошено {rooms_count} "
                    f"({self.display(room_slug)}, {check_in} — {check_out})"
                )

            booking = LocalBooking(
                ref="",
                room_slug=room_slug,
                rooms_count=rooms_count,
                check_in=check_in,
                check_out=check_out,
                guest_name=guest_name.strip(),
                guest_phone=guest_phone.strip(),
                status="booked",
                amount=amount,
                origin=origin,
                note=note.strip(),
            )
            session.add(booking)
            await session.flush()
            booking.ref = f"L-{booking.id:04d}"
            await session.commit()
            await session.refresh(booking)
            return self._to_external(booking)

    async def change_booking(
        self,
        ref: str,
        *,
        check_in: date | None = None,
        check_out: date | None = None,
        rooms_count: int | None = None,
    ) -> ExternalBooking:
        async with self._sessions() as session:
            booking = await self._by_ref(session, ref)
            if booking.status != "booked":
                raise ValueError(f"Бронь {ref} уже отменена — менять нечего")

            new_in = check_in or booking.check_in
            new_out = check_out or booking.check_out
            new_count = rooms_count or booking.rooms_count
            if (new_out - new_in).days <= 0:
                raise ValueError("Дата выезда должна быть позже даты заезда")

            stock = await self._stock(session)
            busy = await self._busy(session, new_in, new_out, skip_ref=ref)
            free = stock.get(booking.room_slug, 0) - busy.get(booking.room_slug, 0)
            if free < new_count:
                raise NotEnoughRooms(
                    f"На новые даты свободно {max(0, free)} — нужно {new_count} "
                    f"({self.display(booking.room_slug)}, {new_in} — {new_out})"
                )

            # Цена пересчитывается пропорционально ночам: шахматка не знает
            # тарифов, но и оставлять сумму от прежних дат нельзя — гость
            # увидит счёт за неделю там, где остался на две ночи.
            old_nights = (booking.check_out - booking.check_in).days
            if booking.amount and old_nights:
                per_night = booking.amount // old_nights
                booking.amount = per_night * (new_out - new_in).days

            booking.check_in = new_in
            booking.check_out = new_out
            booking.rooms_count = new_count
            await session.commit()
            await session.refresh(booking)
            return self._to_external(booking)

    async def cancel_booking(self, ref: str, reason: str = "") -> ExternalBooking:
        async with self._sessions() as session:
            booking = await self._by_ref(session, ref)
            if booking.status == "cancelled":
                return self._to_external(booking)  # повторная отмена — не ошибка
            booking.status = "cancelled"
            booking.cancelled_at = utcnow()
            if reason:
                booking.note = (booking.note + f" | отмена: {reason}").strip(" |")
            await session.commit()
            await session.refresh(booking)
            return self._to_external(booking)

    async def seen_payment(self, ref: str, *, doc_hash: str = "", doc_number: str = "",
                           amount: int = 0) -> bool:
        """Этот платёж уже принимали?"""
        clean = (ref or "").strip().upper()
        async with self._sessions() as session:
            if doc_hash:
                found = await session.execute(
                    select(LocalPayment).where(LocalPayment.doc_hash == doc_hash)
                )
                if found.scalar_one_or_none() is not None:
                    return True
            if doc_number and amount:
                # Тот же документ, но переснятый: байты другие, деньги те же.
                found = await session.execute(
                    select(LocalPayment).where(
                        LocalPayment.booking_ref == clean,
                        LocalPayment.doc_number == doc_number,
                        LocalPayment.amount == amount,
                    )
                )
                if found.scalar_one_or_none() is not None:
                    return True
        return False

    async def mark_paid(
        self,
        ref: str,
        amount: int,
        note: str = "",
        *,
        doc_hash: str = "",
        doc_number: str = "",
        payer: str = "",
    ) -> ExternalBooking:
        """Отметить оплату и запомнить документ, по которому она принята."""
        async with self._sessions() as session:
            booking = await self._by_ref(session, ref)
            booking.paid_amount += max(0, amount)
            if note:
                booking.note = (booking.note + f" | {note}").strip(" |")
            session.add(
                LocalPayment(
                    booking_ref=booking.ref,
                    doc_hash=doc_hash,
                    doc_number=doc_number,
                    amount=max(0, amount),
                    payer=payer,
                )
            )
            await session.commit()
            await session.refresh(booking)
            return self._to_external(booking)

    # ────────────────────────── служебное ──────────────────────────

    async def _by_ref(
        self, session: AsyncSession, ref: str, *, strict: bool = True
    ) -> LocalBooking:
        clean = (ref or "").strip().upper()
        result = await session.execute(select(LocalBooking).where(LocalBooking.ref == clean))
        booking = result.scalar_one_or_none()
        if booking is None and strict:
            raise BookingNotFound(f"Брони {ref} нет")
        return booking

    def _to_external(self, booking: LocalBooking) -> ExternalBooking:
        return ExternalBooking(
            external_id=booking.ref,
            status=booking.status,
            check_in=booking.check_in,
            check_out=booking.check_out,
            total_amount=booking.amount,
            guest_name=booking.guest_name,
            source="stub",
        )

    async def snapshot(self) -> list[dict[str, Any]]:
        """Вся шахматка списком — для отладки и проверки глазами."""
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(LocalBooking).order_by(LocalBooking.check_in, LocalBooking.ref)
                )
            ).scalars().all()
            return [
                {
                    "ref": b.ref,
                    "room": self.display(b.room_slug),
                    "roomSlug": b.room_slug,
                    "rooms": b.rooms_count,
                    "checkIn": b.check_in.isoformat(),
                    "checkOut": b.check_out.isoformat(),
                    "guest": b.guest_name,
                    "phone": b.guest_phone,
                    "status": b.status,
                    "amount": b.amount,
                    "paid": b.paid_amount,
                    "origin": b.origin,
                    "note": b.note,
                }
                for b in rows
            ]
