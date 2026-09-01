"""
╔══════════════════════════════════════════════════════════════════════╗
║  ПЛАТЁЖНЫЙ ШЛЮЗ — МЕСТО ДЛЯ ИНТЕГРАЦИИ БАНКА                        ║
╚══════════════════════════════════════════════════════════════════════╝

Всё, что нужно от банка, читается из переменных окружения (см. .env.example).
Пока они пустые, эндпоинты честно отвечают 501 «не настроено», а сайт
продолжает принимать заявки через форму.

Что должен сделать интегратор со стороны банка:
  1. Заполнить PAYMENT_* в .env (терминал, client_id, client_secret, base_url).
  2. Реализовать два метода в классе своего провайдера ниже:
        · get_token()      — получить access token;
        · create_payment() — создать платёж и вернуть ссылку на оплату.
  3. Проверить подпись колбэка в verify_callback().

Ниже — каркас под Halyk ePay (самый частый эквайер в РК) и заглушка
ForteBank. Названия полей могут отличаться: сверяться с документацией,
которую выдаст банк, менять только внутренности методов.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import timedelta
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .almaty import today as hotel_today

from .config import Settings

logger = logging.getLogger(__name__)


class PaymentError(RuntimeError):
    pass


class PaymentProvider(ABC):
    """Общий интерфейс. Сайт знает только про него, не про конкретный банк."""

    name: str = "abstract"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def create_payment(
        self,
        *,
        order_id: str,
        amount_tenge: int,
        description: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> str:
        """Создаёт платёж в банке и возвращает URL, куда отправить гостя."""

    @abstractmethod
    def verify_callback(self, payload: dict, headers: dict) -> bool:
        """Проверяет, что колбэк действительно пришёл от банка."""

    @staticmethod
    def parse_callback(payload: dict) -> tuple[str | None, str]:
        """Возвращает (order_id, статус: paid|failed|pending) из тела колбэка."""
        raise NotImplementedError


class HalykEpayProvider(PaymentProvider):
    """
    Halyk Bank ePay 2.0.

    Поток: OAuth-токен → создание invoice → редирект гостя на платёжную
    страницу → колбэк с результатом на /api/payments/callback.
    """

    name = "epay_halyk"

    async def get_token(self) -> str:
        s = self.settings
        # ⚠️ ИНТЕГРАТОР: сверить URL и scope с документацией банка.
        url = f"{s.payment_base_url.rstrip('/')}/epay2/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "scope": "webapi usermanagement email_send verification statement statistics payment",
            "client_id": s.payment_client_id,
            "client_secret": s.payment_client_secret,
            "terminal": s.payment_terminal_id,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, data=data)
        if resp.status_code != 200:
            logger.error("Токен не получен: %s %s", resp.status_code, resp.text)
            raise PaymentError("Банк не выдал токен")
        return resp.json()["access_token"]

    async def create_payment(
        self,
        *,
        order_id: str,
        amount_tenge: int,
        description: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> str:
        s = self.settings
        token = await self.get_token()

        # ⚠️ ИНТЕГРАТОР: заменить на актуальный метод создания платежа.
        url = f"{s.payment_base_url.rstrip('/')}/payments/cards/auth"
        body = {
            "amount": amount_tenge,
            "currency": "KZT",
            "invoiceId": order_id,
            "description": description,
            "terminal": s.payment_terminal_id,
            "backLink": s.payment_success_url,
            "failureBackLink": s.payment_failure_url,
            "postLink": f"{s.payment_base_url}/api/payments/callback",
            "email": email,
            "phone": phone,
        }
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code >= 400:
            logger.error("Платёж не создан: %s %s", resp.status_code, resp.text)
            raise PaymentError("Банк отклонил создание платежа")

        payload = resp.json()
        pay_url = payload.get("paymentUrl") or payload.get("redirectUrl")
        if not pay_url:
            raise PaymentError("Банк не вернул ссылку на оплату")
        return pay_url

    def verify_callback(self, payload: dict, headers: dict) -> bool:
        # ⚠️ ИНТЕГРАТОР: подставить проверку подписи из документации банка
        # (обычно HMAC по телу запроса секретом PAYMENT_WEBHOOK_SECRET).
        secret = self.settings.payment_webhook_secret
        if not secret:
            logger.warning("PAYMENT_WEBHOOK_SECRET не задан — подпись не проверяется")
            return True
        return headers.get("x-signature", "") == secret

    @staticmethod
    def parse_callback(payload: dict) -> tuple[str | None, str]:
        order_id = payload.get("invoiceId") or payload.get("orderId")
        code = str(payload.get("code", payload.get("status", ""))).lower()
        if code in {"ok", "success", "0", "paid", "auth"}:
            return order_id, "paid"
        if code in {"pending", "processing"}:
            return order_id, "pending"
        return order_id, "failed"


class ForteBankProvider(HalykEpayProvider):
    """
    ForteBank. Расчётный счёт отеля открыт в ForteBank, поэтому
    эквайринг, скорее всего, будет от него же.
    Протокол близок к ePay — методы наследуются; при расхождениях
    переопределить create_payment() и parse_callback().
    """

    name = "fortebank"


class FreedomPayProvider(PaymentProvider):
    """
    FreedomPay (Казахстан), протокол Merchant API.

    Отличается от Halyk и Forte тем, что не использует OAuth: каждый запрос
    подписывается MD5-подписью из его собственных полей и секретного слова.
    Токен получать не нужно, зато подпись обязана совпасть до символа.

    Как считается подпись (docs.freedompay.kz → Merchant API → Введение):

        имя_скрипта ; поля_по_алфавиту ; секретное_слово

    Всё через точку с запятой, MD5 в нижнем регистре. Тонкость, на которой
    ошибаются чаще всего: **в подпись входят ВСЕ поля запроса**, включая те,
    что добавили сверх документации. Добавил параметр и забыл про подпись —
    получишь отказ без объяснения причины.

    Вторая тонкость: сортировка по имени поля, а не по порядку в запросе.
    """

    name = "freedompay"
    BASE = "https://api.freedompay.kz"

    def _sign(self, script: str, fields: dict[str, Any]) -> str:
        """Подпись запроса или проверка ответа — считается одинаково."""
        # pg_sig в подпись не входит: его как раз и вычисляем.
        parts = [script] + [
            str(fields[k]) for k in sorted(fields) if k != "pg_sig"
        ] + [self.settings.payment_client_secret]
        return hashlib.md5(";".join(parts).encode("utf-8")).hexdigest()

    async def get_status(self, *, payment_id: str = "", order_id: str = "") -> dict[str, str]:
        """Что стало с платежом: списан, ждёт, отменён, возвращён.

        Нужно ровно для одного вопроса, который задают чаще всех: «страница
        показала успешную оплату, а денег на счёте нет — где они?». Ответ
        обычно в статусе: авторизация (холд) списанием не является, а
        возврат по отменённой броне мог уже уйти и просто ещё не дошёл до
        карты — банки возвращают деньги днями, а не минутами.

        Спрашивать у поддержки то, что отдаёт их же API, — терять сутки на
        каждый вопрос.

        Достаточно одного из двух: номера платежа или номера заказа.
        """
        script = "get_status3.php"
        fields: dict[str, Any] = {
            "pg_merchant_id": self.settings.payment_terminal_id,
            "pg_salt": secrets.token_hex(8),
        }
        if payment_id:
            fields["pg_payment_id"] = str(payment_id)
        if order_id:
            fields["pg_order_id"] = str(order_id)
        if not payment_id and not order_id:
            raise PaymentError("Нужен номер платежа или номер заказа")
        fields["pg_sig"] = self._sign(script, fields)

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(f"{self.BASE}/{script}", data=fields)
                response.raise_for_status()
                body = response.text
        except Exception as error:  # noqa: BLE001
            logger.warning("FreedomPay не ответил на запрос статуса: %s", error)
            raise PaymentError(f"FreedomPay недоступен: {error}") from error

        if _tag(body, "pg_status") != "ok":
            code = _tag(body, "pg_error_code")
            message = _tag(body, "pg_error_description") or "без описания"
            raise PaymentError(f"FreedomPay отказал ({code}): {message}")

        # Забираем всё, что пришло: набор полей у разных статусов разный, и
        # выбирать заранее значит однажды не увидеть главного.
        out: dict[str, str] = {}
        for поле in (
            "pg_payment_id", "pg_order_id", "pg_transaction_status",
            "pg_payment_status", "pg_amount", "pg_currency", "pg_net_amount",
            "pg_ps_amount", "pg_ps_currency", "pg_captured", "pg_refund_amount",
            "pg_revoked_amount", "pg_card_pan", "pg_create_date",
            "pg_payment_date", "pg_capture_date", "pg_refund_date",
            "pg_failure_code", "pg_failure_description", "pg_card_brand",
        ):
            значение = _tag(body, поле)
            if значение:
                out[поле] = значение
        return out

    async def find_payment(self, *, needle: str, days: int = 400) -> dict[str, str]:
        """Найти платёж по тексту в описании заказа.

        Нужно потому, что платёж создаём не мы: гостя на страницу банка
        отправляет модуль Exely, и его номер заказа (PG1798) нам неизвестен.
        Зато в описании платежа Exely пишет номер брони целиком — по нему и
        ищем. Другого способа связать бронь с платежом нет: в данных брони
        Exely отдаёт сумму предоплаты и способ оплаты, но не идентификатор
        транзакции.

        ⚠️ ПРОВЕРЕНО НА БОЕВОМ МАГАЗИНЕ 2026-09-01: НЕ РАБОТАЕТ.

        `get_transactions_list.php`, `get_transactions.php` и `register.php`
        отвечают HTTP 403 и HTML-страницей, а не ошибкой API. Так сервер
        отвечает на несуществующий адрес — значит метода выборки транзакций
        в Merchant API попросту нет. В документации его тоже нет: раздел
        «После платежа» описывает только `get_status3.php`, `do_capture.php`,
        `cancel.php` и `revoke.php`, и все они работают.

        Следствие: связать бронь с платежом автоматически нечем. Номер брони
        Exely пишет в описание заказа, но искать по описанию негде, а
        собственный номер заказа Exely (вида PG1798) нам неизвестен —
        платёж создаём не мы.

        Метод оставлен намеренно: он честно возвращает «поиск недоступен», и
        на этом строится сообщение отелю. Заработает — если поддержка
        FreedomPay включит выборку транзакций для магазина; тогда достаточно
        снять это предупреждение.
        """
        script = "get_transactions_list.php"
        # Время отеля, а не машины: сервер живёт в UTC, и в первые пять
        # часов суток по Алматы «сегодня» разъезжается на день.
        today = hotel_today()
        fields: dict[str, Any] = {
            "pg_merchant_id": self.settings.payment_terminal_id,
            "pg_date_from": (today - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00"),
            "pg_date_to": (today + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"),
            "pg_salt": secrets.token_hex(8),
        }
        fields["pg_sig"] = self._sign(script, fields)

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                response = await client.post(f"{self.BASE}/{script}", data=fields)
                # Не падаем на коде ответа: у несуществующего адреса
                # тело говорит больше, чем номер ошибки.
                body = response.text
        except Exception as error:  # noqa: BLE001
            raise PaymentError(f"FreedomPay недоступен: {error}") from error

        # 403 с HTML вместо XML — адреса не существует. Отдельная ветка,
        # чтобы в сообщении отелю не мелькала разметка страницы ошибки.
        if body.lstrip().startswith("<!DOCTYPE") or "<html" in body[:200].lower():
            raise PaymentError("выборка транзакций недоступна для этого магазина")
        if _tag(body, "pg_error_description"):
            raise PaymentError(
                f"поиск платежей недоступен: {_tag(body, 'pg_error_description')}")

        # Ответ — список <transaction>…</transaction>. Разбираем построчно:
        # тащить XML-парсер ради нескольких полей незачем, формат стабилен.
        for chunk in body.split("<transaction>")[1:]:
            block = chunk.split("</transaction>")[0]
            if needle not in block:
                continue
            found: dict[str, str] = {}
            for поле in ("pg_payment_id", "pg_order_id", "pg_amount", "pg_currency",
                         "pg_status", "pg_payment_status", "pg_description",
                         "pg_card_pan", "pg_create_date", "pg_captured",
                         "pg_refund_amount", "pg_revoked_amount"):
                значение = _tag(block, поле)
                if значение:
                    found[поле] = значение
            if found:
                return found
        return {}

    async def refund(self, *, payment_id: str, amount_tenge: int = 0,
                     idempotency: str = "") -> dict[str, str]:
        """Вернуть деньги по платежу. Нулевая сумма — возврат целиком.

        Настоящее движение денег. Метод ничего не решает и ничего не считает:
        сумму и право на возврат определяет вызывающий, и решение к этому
        моменту должно быть уже записано.

        `idempotency` — ключ повтора (`pg_idempotency_key` в документации
        FreedomPay). С ним банк сам отклонит второй такой же возврат, даже
        если наш код отправит его дважды: при обрыве связи, при повторном
        уведомлении об отмене, при ручном запуске поверх автоматического.
        Собственная защита от повтора у нас есть, но она смотрит на данные,
        которые могли устареть, а эта — на стороне банка и надёжнее.
        """
        script = "revoke.php"
        fields: dict[str, Any] = {
            "pg_merchant_id": self.settings.payment_terminal_id,
            "pg_payment_id": str(payment_id),
            "pg_salt": secrets.token_hex(8),
        }
        if amount_tenge > 0:
            fields["pg_refund_amount"] = str(amount_tenge)
        if idempotency:
            fields["pg_idempotency_key"] = str(idempotency)[:120]
        fields["pg_sig"] = self._sign(script, fields)

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                response = await client.post(f"{self.BASE}/{script}", data=fields)
                response.raise_for_status()
                body = response.text
        except Exception as error:  # noqa: BLE001
            raise PaymentError(f"FreedomPay недоступен: {error}") from error

        if _tag(body, "pg_status") != "ok":
            code = _tag(body, "pg_error_code")
            message = _tag(body, "pg_error_description") or "без описания"
            raise PaymentError(f"Возврат не прошёл ({code}): {message}")
        return {
            "payment_id": str(payment_id),
            "amount": str(amount_tenge or ""),
            "message": _tag(body, "pg_status_description") or "принят",
        }


    async def create_payment(
        self,
        *,
        order_id: str,
        amount_tenge: int,
        description: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> str:
        script = "init_payment.php"
        fields: dict[str, Any] = {
            "pg_order_id": order_id,
            "pg_merchant_id": self.settings.payment_terminal_id,
            "pg_amount": str(amount_tenge),
            "pg_currency": "KZT",
            "pg_description": description[:255],
            "pg_salt": secrets.token_hex(8),
            "pg_success_url": self.settings.payment_success_url,
            "pg_failure_url": self.settings.payment_failure_url,
            "pg_result_url": self.settings.payment_result_url,
            # Просим не автосписание, а обычную оплату с формы банка.
            "pg_testing_mode": "1" if self.settings.payment_testing else "0",
        }
        if email:
            fields["pg_user_contact_email"] = email
        if phone:
            fields["pg_user_phone"] = "".join(c for c in phone if c.isdigit())

        fields["pg_sig"] = self._sign(script, fields)

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(f"{self.BASE}/{script}", data=fields)
                response.raise_for_status()
                body = response.text
        except Exception as error:  # noqa: BLE001
            logger.warning("FreedomPay не ответил: %s", error)
            raise PaymentError(f"FreedomPay недоступен: {error}") from error

        # Ответ приходит XML — тащить ради него парсер незачем, полей два.
        status = _tag(body, "pg_status")
        if status != "ok":
            code = _tag(body, "pg_error_code")
            message = _tag(body, "pg_error_description") or "без описания"
            logger.warning("FreedomPay отказал: код %s, %s", code, message)
            raise PaymentError(f"FreedomPay отказал ({code}): {message}")

        url = _tag(body, "pg_redirect_url")
        if not url:
            raise PaymentError("FreedomPay не вернул ссылку на оплату")
        return url

    def verify_callback(self, payload: dict, headers: dict) -> bool:
        """Уведомление подписано тем же способом, что и запрос.

        Проверять обязательно: адрес уведомления открыт интернету, и без
        проверки подписи любой желающий мог бы объявить бронь оплаченной.
        """
        got = str(payload.get("pg_sig") or "")
        if not got:
            return False
        # Имя скрипта в подписи уведомления — последняя часть нашего
        # result_url, а не init_payment.php.
        script = self.settings.payment_result_url.rstrip("/").rsplit("/", 1)[-1]
        return secrets.compare_digest(got.lower(), self._sign(script, payload))

    @staticmethod
    def parse_callback(payload: dict) -> tuple[str | None, str]:
        order = payload.get("pg_order_id")
        result = str(payload.get("pg_result") or "")
        # pg_result: 1 — оплачено, 0 — отказ. Всё прочее считаем «в процессе»:
        # объявлять бронь оплаченной по незнакомому коду нельзя.
        status = {"1": "paid", "0": "failed"}.get(result, "pending")
        return (str(order) if order else None, status)


def _tag(xml: str, name: str) -> str:
    """Значение одного тега из плоского XML-ответа."""
    start, end = f"<{name}>", f"</{name}>"
    if start not in xml or end not in xml:
        return ""
    return xml.split(start, 1)[1].split(end, 1)[0].strip()


def get_provider(settings: Settings) -> PaymentProvider | None:
    if not settings.payment_configured:
        return None
    providers = {
        "epay_halyk": HalykEpayProvider,
        "fortebank": ForteBankProvider,
        "freedompay": FreedomPayProvider,
    }
    cls = providers.get(settings.payment_provider)
    if cls is None:
        logger.error("Неизвестный PAYMENT_PROVIDER=%s", settings.payment_provider)
        return None
    return cls(settings)


def new_order_id() -> str:
    """Номер заказа для банка. Многие банки требуют не длиннее 20 символов."""
    return uuid.uuid4().hex[:20]
