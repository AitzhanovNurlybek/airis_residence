"""
Официальное API Exely: настоящие брони гостей.

Это не то же самое, что `exely.py`. Там мы читаем наличие с адреса, который
подсмотрен у виджета: он открыт, но нам его никто не обещал. Здесь —
договорной доступ по OAuth, который выдают в кабинете отеля, и по нему видны
брони конкретного гостя.

Зачем это нужно. Гость пишет в час ночи «у меня бронь стоит?» — и сегодня
консьерж отвечает «уточнит стойка», потому что не видит ничего. С этим
модулем он отвечает по существу: даты, категория, статус, сумма.

Чего здесь нет и не будет: создания брони. Такого метода в Exely нет вовсе —
разбор в `docs/EXELY_API.md`. Бронь рождается только в форме.

⚠️ Разбор ответов написан по документации, но живых ответов Exely мы ещё не
видели: доступ не выдан. Поля читаются мягко — чего нет, то не ломает разбор,
а превращается в пустое значение. При первом подключении прогнать
`python exely_check.py` и сверить, что поля называются так, как здесь.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

import httpx

from .base import BookingSystemUnavailable, ExternalBooking

logger = logging.getLogger(__name__)

#: За сколько секунд до истечения просим новый токен. Токен живёт всего
#: 15 минут (900 секунд) и без обновления — по документации Exely его
#: разрешено только перевыпускать заново. Запрос на самой границе срока
#: иногда прилетает уже просроченным, отсюда запас.
TOKEN_MARGIN = 60.0

NOT_CONFIGURED = (
    "Официальный доступ к Exely не настроен. Нужны EXELY_CLIENT_ID, "
    "EXELY_CLIENT_SECRET, EXELY_PROPERTY_ID, EXELY_AUTH_URL и EXELY_API_BASE "
    "в backend/.env — их выдают в кабинете: Настройки гостиницы → "
    "Подключения API → Создать подключение."
)


def _digits(value: str) -> str:
    return "".join(c for c in str(value or "") if c.isdigit())


def _tail(phone: str) -> str:
    """Последние девять цифр.

    Один и тот же номер приходит как +7 777 531-00-09, 87775310009 и
    77775310009. Совпадение по хвосту переживает и код страны, и восьмёрку.
    """
    return _digits(phone)[-9:]


def _as_date(value: Any) -> date | None:
    """Дата из чего угодно, что присылают API: с временем, с зоной, без."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    for attempt in (text, text[:10]):
        try:
            return datetime.fromisoformat(attempt).date()
        except ValueError:
            continue
    return None


def _money(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _first(source: dict[str, Any], *names: str) -> Any:
    """Первое непустое поле из перечисленных.

    В документации одно и то же поле в разных API называется по-разному
    (`number` и `reservationNumber`, `arrivalDate` и `checkInDate`). Пока не
    увидели живой ответ, читаем все известные написания — это дешевле, чем
    сломаться на первом же запросе в бою.
    """
    for name in names:
        value = source.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


class ExelyApi:
    """Клиент официального API. Только чтение."""

    name = "Exely API (брони)"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        property_id: str,
        *,
        auth_url: str,
        api_base: str,
        timeout: float = 15.0,
    ) -> None:
        if not all((client_id, client_secret, property_id, auth_url, api_base)):
            raise BookingSystemUnavailable(NOT_CONFIGURED)
        self._id = client_id
        self._secret = client_secret
        self._property = str(property_id).strip()
        self._auth = auth_url.rstrip("/")
        self._base = api_base.rstrip("/")
        self._timeout = timeout
        self._token: str = ""
        self._expires: float = 0.0

    # ─────────────────────────────── доступ ───────────────────────────────

    async def token(self) -> str:
        """Токен доступа. Держим до истечения, а не берём на каждый запрос."""
        if self._token and time.monotonic() < self._expires - TOKEN_MARGIN:
            return self._token

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._auth,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._id,
                        "client_secret": self._secret,
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as error:  # noqa: BLE001 — причина не влияет на действие
            # Ключ в сообщение не попадает: этот текст видит и админка, и лог.
            logger.warning("Exely не выдал токен: %s", type(error).__name__)
            raise BookingSystemUnavailable(
                "Exely не выдал токен доступа. Проверь EXELY_CLIENT_ID и "
                "EXELY_CLIENT_SECRET и срок действия подключения."
            ) from error

        token = str(_first(payload, "access_token", "accessToken") or "")
        if not token:
            raise BookingSystemUnavailable(
                "Exely ответил без токена — проверь адрес EXELY_AUTH_URL."
            )

        try:
            # Запасное значение — тоже 15 минут, а не час: столько документация
            # обещает, если поле вдруг не придёт в ответе.
            lifetime = float(_first(payload, "expires_in", "expiresIn") or 900)
        except (TypeError, ValueError):
            lifetime = 900.0

        self._token = token
        self._expires = time.monotonic() + lifetime
        return token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {await self.token()}",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params or {}, headers=headers)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except BookingSystemUnavailable:
            raise
        except Exception as error:  # noqa: BLE001
            logger.warning("Exely не ответил на %s: %s", path, error)
            raise BookingSystemUnavailable(f"Exely не ответил: {error}") from error

    # ──────────────────────────────── брони ────────────────────────────────

    async def get_booking(self, number: str) -> ExternalBooking | None:
        """Одна бронь по номеру. None — такой брони нет."""
        number = str(number or "").strip()
        if not number:
            return None
        data = await self._get(f"/v1/properties/{self._property}/bookings/{number}")
        if not isinstance(data, dict):
            return None
        # Документация подтверждена: ответ обёрнут в {"booking": {...}},
        # а не отдаёт бронь на верхнем уровне. Раньше код читал данные из
        # обёртки целиком — все поля оказывались бы None, и бронь молча
        # пропадала бы, хотя запрос прошёл успешно.
        booking = data.get("booking")
        if not isinstance(booking, dict):
            return None
        return self._booking(booking)

    async def find_bookings(self, *, phone: str = "", name: str = "") -> list[ExternalBooking]:
        """Брони гостя.

        Телефон — из канала связи, а не из текста переписки: написанному
        «это моя бронь» верить нельзя, иначе чужую бронь покажет любой, кто
        назовёт номер.
        """
        tail = _tail(phone)
        if not tail:
            return []

        data = await self._get(
            f"/v1/properties/{self._property}/bookings",
            {"phone": phone, "guestName": name} if name else {"phone": phone},
        )
        rows = self._rows(data)

        # Фильтруем на своей стороне даже после запроса с телефоном: если
        # параметр поиска называется иначе, чем мы думаем, Exely молча вернёт
        # все брони отеля — и консьерж покажет гостю чужие.
        mine: list[ExternalBooking] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if tail and tail not in _digits(self._phone_of(row)):
                continue
            booking = self._booking(row)
            if booking is not None:
                mine.append(booking)
        return mine

    # ─────────────────────────────── разбор ───────────────────────────────

    @staticmethod
    def _rows(data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # bookingSummaries — подтверждённое имя из документации
            # («Get booking summaries»). Остальные — на случай, если у
            # других версий API оно называется иначе.
            for key in ("bookingSummaries", "bookings", "reservations", "items",
                       "data", "results"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _phone_of(row: dict[str, Any]) -> str:
        direct = _first(row, "phone", "phoneNumber", "contactPhone")
        if direct:
            return str(direct)
        # Порядок важен, но пустое поле не должно прерывать поиск: раньше
        # отсутствующий `guest` превращался в {}, проверка isinstance проходила
        # и функция возвращала пустую строку, ни разу не заглянув в список
        # `guests`. Бронь с телефоном внутри списка считалась чужой.
        guest = _first(row, "guest", "customer", "mainGuest")
        if isinstance(guest, dict):
            found = _first(guest, "phone", "phoneNumber", "contactPhone")
            if found:
                return str(found)
        guests = _first(row, "guests")
        if isinstance(guests, list):
            for item in guests:
                if isinstance(item, dict):
                    found = _first(item, "phone", "phoneNumber", "contactPhone")
                    if found:
                        return str(found)
        return ""

    @staticmethod
    def _guest_name(row: dict[str, Any]) -> str:
        # Та же ловушка, что и с телефоном: пустой `guest` не должен закрывать
        # дорогу к списку `guests`.
        candidates: list[Any] = []
        one = _first(row, "guest", "customer", "mainGuest")
        if isinstance(one, dict):
            candidates.append(one)
        many = _first(row, "guests")
        if isinstance(many, list):
            candidates.extend(g for g in many if isinstance(g, dict))

        for guest in candidates:
            whole = _first(guest, "fullName", "name")
            if whole:
                return str(whole)
            parts = [
                str(guest.get(k) or "").strip()
                for k in ("lastName", "firstName", "middleName")
            ]
            joined = " ".join(p for p in parts if p)
            if joined:
                return joined
        return str(_first(row, "guestName", "customerName") or "")

    def _booking(self, row: dict[str, Any]) -> ExternalBooking | None:
        # Подтверждено документацией: у полной брони дат на верхнем уровне
        # нет вовсе — они лежат внутри каждого элемента roomStays (бронь может
        # включать несколько проживаний с разными периодами). У краткой
        # сводки (bookingSummaries) точная форма не показана примером, поэтому
        # сначала пробуем верхний уровень на случай, если она плоская, и
        # только потом идём в roomStays.
        check_in = _as_date(_first(row, "arrivalDate", "checkInDate", "checkIn", "startDate"))
        check_out = _as_date(_first(row, "departureDate", "checkOutDate", "checkOut", "endDate"))
        if check_in is None or check_out is None:
            stays = row.get("roomStays")
            if isinstance(stays, list):
                ins = [
                    d for stay in stays if isinstance(stay, dict)
                    for d in [_as_date(_first(stay, "arrivalDate", "checkInDate", "checkIn"))]
                    if d is not None
                ]
                outs = [
                    d for stay in stays if isinstance(stay, dict)
                    for d in [_as_date(_first(stay, "departureDate", "checkOutDate", "checkOut"))]
                    if d is not None
                ]
                # Несколько проживаний — берём весь период целиком: от самого
                # раннего заезда до самого позднего выезда.
                if ins:
                    check_in = min(ins)
                if outs:
                    check_out = max(outs)

        number = _first(row, "number", "reservationNumber", "bookingNumber", "id")

        # Бронь без номера или без дат показывать гостю нельзя: он спросит
        # «а какие даты?», и ответить будет нечем.
        if not number or check_in is None or check_out is None:
            logger.warning("Exely прислал бронь без номера или дат — пропускаю")
            return None

        amount = _first(row, "totalAmount", "total", "amount", "totalPrice")
        if isinstance(amount, dict):
            amount = _first(amount, "amount", "value", "gross")

        return ExternalBooking(
            external_id=str(number),
            status=str(_first(row, "status", "state", "bookingStatus") or "unknown"),
            check_in=check_in,
            check_out=check_out,
            total_amount=_money(amount),
            guest_name=self._guest_name(row),
            source="exely",
        )
