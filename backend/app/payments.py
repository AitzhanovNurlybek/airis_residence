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

import logging
import uuid
from abc import ABC, abstractmethod

import httpx

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


def get_provider(settings: Settings) -> PaymentProvider | None:
    if not settings.payment_configured:
        return None
    providers = {
        "epay_halyk": HalykEpayProvider,
        "fortebank": ForteBankProvider,
    }
    cls = providers.get(settings.payment_provider)
    if cls is None:
        logger.error("Неизвестный PAYMENT_PROVIDER=%s", settings.payment_provider)
        return None
    return cls(settings)


def new_order_id() -> str:
    """Номер заказа для банка. Многие банки требуют не длиннее 20 символов."""
    return uuid.uuid4().hex[:20]
