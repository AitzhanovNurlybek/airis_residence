"""
Рабочая схема на сегодня: наличие настоящее, бронь уходит заявкой.

Пока Exely отдаёт только чтение, у нас два неполных куска. Из Exely видно, что
свободно на самом деле, но записать туда нечего. В свою базу писать можно, но
её наличие выдумано. По отдельности оба бесполезны для живого гостя: первый
умеет только рассказывать, второй — уверенно врать.

Здесь они сложены так, как отель работает и без нас. Наличие спрашиваем у
Exely — это правда. Бронь кладём заявкой менеджеру, ровно как это делает форма
на сайте: он проверяет, подтверждает и вносит в шахматку. Гостю честно
говорится, что номер подтвердит человек.

Почему это лучше, чем ждать API. Ночью и в выходные гость сейчас не получает
вообще ничего: менеджер спит, форма молчит. С этой схемой он в час ночи
узнаёт, что свободен Comfort, оставляет заявку и получает её номер. Утром
менеджер видит готовую заявку с проверенным наличием, а не «перезвоните».

Что появится с приходом настоящего API: заявка станет бронью сразу, без
ночного ожидания. Всё остальное — те же вызовы, тот же разговор.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..almaty import today as hotel_today
from ..db import Lead
from .base import Availability, BookingSystemUnavailable, ExternalBooking, ExternalInvoice
from .exely import ExelyBookingSystem

logger = logging.getLogger(__name__)


class HybridBookingSystem:
    """Наличие из Exely, брони — заявками менеджеру."""

    name = "Exely + заявки менеджеру"

    #: Заявки живут в нашей базе и ищутся по телефону, номера короткие
    #: (Z-0007). Отдавать заявку по одному номеру нельзя.
    finds_by_phone = True
    source = "exely"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        room_names: dict[str, str] | None = None,
        hotel_code: str = "",
    ) -> None:
        self._sessions = session_factory
        self._names = room_names or {}
        self._exely = ExelyBookingSystem(
            hotel_code=hotel_code or "509506", room_names=room_names
        )

    def display(self, slug: str) -> str:
        return self._exely.display(slug)

    # ─────────────────────────── чтение ────────────────────────────

    async def availability(self, check_in: date, check_out: date, *,
                           guests: int = 2) -> Availability:
        return await self._exely.availability(check_in, check_out, guests=guests)

    async def get_booking(self, external_id: str) -> ExternalBooking | None:
        async with self._sessions() as session:
            lead = await self._by_ref(session, external_id)
            return self._to_external(lead) if lead else None

    async def find_bookings(self, *, phone: str = "", name: str = "") -> list[ExternalBooking]:
        digits = "".join(c for c in phone if c.isdigit())
        if not digits:
            return []
        tail = digits[-9:]

        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(Lead).where(Lead.source == "concierge").order_by(Lead.id.desc())
                )
            ).scalars().all()

        # Сравниваем по последним девяти цифрам: один и тот же номер приходит
        # то с +7, то с 8, то вовсе без кода страны.
        return [
            self._to_external(lead)
            for lead in rows
            if "".join(c for c in (lead.phone or "") if c.isdigit()).endswith(tail)
        ]

    async def invoices(self, *, company_bin: str = "", external_id: str = ""):
        # Счета выставляет менеджер вручную — заявка их не порождает.
        return []

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
        origin: str = "concierge",
        note: str = "",
    ) -> ExternalBooking:
        """
        Оставить заявку менеджеру.

        Наличие перепроверяется прямо здесь, перед записью, а не только в
        разговоре. Между «посмотрели» и «оформляем» проходят минуты, и за это
        время номер может уйти другому каналу — тогда гость получит заявку на
        то, чего уже нет.

        Если Exely в этот момент не ответил, заявку всё равно принимаем. Отказ
        гостю из-за чужой недоступности хуже, чем заявка, которую менеджер
        проверит руками; в примечании об этом честно сказано.
        """
        if (check_out - check_in).days <= 0:
            raise ValueError("Дата выезда должна быть позже даты заезда")

        warning = ""
        try:
            free = await self._exely.availability(check_in, check_out)
            offer = next((o for o in free.offers if o.room_slug == room_slug), None)
            left = offer.rooms_left if offer else 0
            if not left:
                raise ValueError(
                    f"{self.display(room_slug)} на {check_in} — {check_out} уже занят"
                )
            if left < rooms_count:
                raise ValueError(
                    f"Свободно только {left} — {self.display(room_slug)}, запрошено {rooms_count}"
                )
        except BookingSystemUnavailable as error:
            logger.warning("Наличие не перепроверено: %s", error)
            warning = " Наличие не перепроверено: система бронирования не ответила."

        nights = (check_out - check_in).days
        comment = (
            f"Заявка от ИИ-консьержа. {self.display(room_slug)} × {rooms_count}, "
            f"{nights} ноч., ориентировочно {amount} ₸."
            + (f" {note}" if note else "")
            + warning
        )

        async with self._sessions() as session:
            lead = Lead(
                name=guest_name.strip() or "Гость из переписки",
                phone=guest_phone.strip(),
                check_in=check_in.isoformat(),
                check_out=check_out.isoformat(),
                adults=0,
                room=room_slug,
                comment=comment,
                status="new",
                source="concierge",
            )
            session.add(lead)
            await session.commit()
            await session.refresh(lead)
            return self._to_external(lead, amount=amount)

    async def cancel_booking(self, ref: str, reason: str = "") -> ExternalBooking:
        async with self._sessions() as session:
            lead = await self._by_ref(session, ref)
            if lead is None:
                raise ValueError(f"Заявки {ref} нет")
            lead.status = "cancelled"
            lead.comment = ((lead.comment or "") + f" | отмена: {reason or 'по просьбе гостя'}").strip(" |")
            await session.commit()
            await session.refresh(lead)
            return self._to_external(lead)

    async def change_booking(
        self,
        ref: str,
        *,
        check_in: date | None = None,
        check_out: date | None = None,
        rooms_count: int | None = None,
    ) -> ExternalBooking:
        """
        Перенос заявки.

        Менять можно только то, что менеджер ещё не взял в работу. Заявку,
        которую уже подтвердили и внесли в шахматку, консьерж трогать не
        должен: гость получит одно, а в отеле будет другое.
        """
        async with self._sessions() as session:
            lead = await self._by_ref(session, ref)
            if lead is None:
                raise ValueError(f"Заявки {ref} нет")
            if lead.status not in ("new", ""):
                raise ValueError(
                    f"Заявку {ref} уже взял менеджер — изменения только через стойку"
                )

            new_in = check_in or date.fromisoformat(lead.check_in or hotel_today().isoformat())
            new_out = check_out or date.fromisoformat(lead.check_out or hotel_today().isoformat())
            if (new_out - new_in).days <= 0:
                raise ValueError("Дата выезда должна быть позже даты заезда")

            lead.check_in = new_in.isoformat()
            lead.check_out = new_out.isoformat()
            if rooms_count:
                lead.comment = ((lead.comment or "") + f" | номеров: {rooms_count}").strip(" |")
            await session.commit()
            await session.refresh(lead)
            return self._to_external(lead)

    # ────────────────────────── служебное ──────────────────────────

    async def _by_ref(self, session: AsyncSession, ref: str) -> Lead | None:
        number = _lead_id(ref)
        if number is None:
            return None
        lead = await session.get(Lead, number)
        if lead is None or lead.source != "concierge":
            return None
        return lead

    def _to_external(self, lead: Lead, amount: int = 0) -> ExternalBooking:
        return ExternalBooking(
            external_id=f"Z-{lead.id:04d}",
            status="cancelled" if lead.status == "cancelled" else "booked",
            check_in=date.fromisoformat(lead.check_in) if lead.check_in else hotel_today(),
            check_out=date.fromisoformat(lead.check_out) if lead.check_out else hotel_today(),
            total_amount=amount,
            guest_name=lead.name or "",
            source="exely",
        )


def _lead_id(ref: str) -> int | None:
    """«Z-0007» → 7. Заявки нумеруются иначе, чем брони, чтобы не путать."""
    digits = "".join(c for c in (ref or "") if c.isdigit())
    return int(digits) if digits else None
