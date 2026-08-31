"""
Возврат денег при отмене брони.

Отмену бронирования делает отель — в шахматке или в отчёте Exely. А деньги
возвращает бухгалтерия вручную: связки между Exely и банком нет, и, по
прямому ответу поддержки Exely, не будет — гостя переводят на страницу
банка, а дальше Exely платёж не видит.

Отсюда и берётся разрыв, который здесь закрывается. Бронь отменена, гость
ждёт денег, а сделать возврат может только человек, который зайдёт в кабинет
банка, найдёт нужную транзакцию среди сотен и посчитает сумму с учётом
штрафа. Пока он это делает, гость пишет «где мои деньги».

────────────────────────────────────────────────────────────────────────
КАК СЧИТАЕТСЯ СУММА

Не нами. Exely в данных отменённой брони отдаёт две величины:

    guaranteeInfo.totalPrepaid    сколько гость заплатил
    cancellation.penaltyAmount    сколько удержано по правилам отеля

Возврат — их разность. Это важно: правила отмены живут в Exely, там их
меняет отель, и дублировать их здесь значило бы однажды вернуть не ту
сумму. Если Exely удержал всё (поздняя отмена), разность равна нулю, и
возвращать нечего — это тоже ответ.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ ПО УМОЛЧАНИЮ НИЧЕГО НЕ ВОЗВРАЩАЕТСЯ

Это движение чужих денег без участия человека. Ошибка здесь не оставляет
следа в виде «гость не получил ответа» — она оставляет след в виде
недостачи, и заметят её нескоро.

Поэтому по умолчанию модуль ТОЛЬКО СЧИТАЕТ и присылает отелю готовое
решение: вот бронь, вот платёж, вот сумма к возврату, вот номер транзакции.
Человеку остаётся нажать одну кнопку вместо получаса поисков. Автоматически
деньги уходят, лишь когда отель это явно включил (`REFUND_AUTO=1`) и сумма
не больше разрешённого предела.

Второй предохранитель — предел суммы. Одна опечатка в правилах Exely не
должна приводить к возврату на сотни тысяч без единого человеческого
взгляда.

────────────────────────────────────────────────────────────────────────
ОТМЕНА — НЕ ОКОНЧАТЕЛЬНОЕ СОСТОЯНИЕ

Из инструкции Exely (kb282396): «Если в полученном письме гость подтвердит
проживание, бронирование будет автоматически восстановлено».

То есть между отменой и возвратом бронь может ожить, а деньги к тому
моменту уже уйдут. Поэтому перед отправкой статус брони перечитывается
заново: то, что было верно при расчёте, к моменту отправки может стать
неверным.

Это же — причина не включать автоматический возврат сразу. Пока отель
нажимает кнопку сам, восстановленную бронь он увидит своими глазами.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ ВОЗВРАТ ВООБЩЕ РУЧНОЙ

Там же у Exely: возврат нужно делать самостоятельно, если гость платил
«через эквайринг средства размещения» — то есть через собственный договор
отеля с банком. «В остальных случаях возврат происходит автоматически».

У отеля именно свой эквайринг (FreedomPay, магазин 570767), поэтому Exely
и не возвращает деньги сам. Этот модуль закрывает разрыв, а устранить его
целиком можно только переходом на эквайринг самого Exely — но это уже
решение про деньги и договор, не про код.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .payments import PaymentError, get_provider

logger = logging.getLogger(__name__)


@dataclass
class RefundPlan:
    """Что делать с деньгами по отменённой броне."""

    booking: str
    prepaid: int = 0
    penalty: int = 0
    amount: int = 0
    payment_id: str = ""
    card: str = ""
    already_refunded: int = 0
    problem: str = ""

    @property
    def due(self) -> bool:
        """Есть ли что возвращать."""
        return self.amount > 0 and bool(self.payment_id) and not self.problem


def _money(value: Any) -> int:
    """Сумма в целых тенге. Exely отдаёт дробное, банк принимает целое."""
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def plan_refund(booking: dict[str, Any], payment: dict[str, str]) -> RefundPlan:
    """Посчитать возврат по данным брони и найденному платежу.

    Отдельная функция без обращений к сети: это единственное место, где
    решается судьба денег, и проверять его надо без банка и без Exely.
    """
    number = str(booking.get("number") or "")
    guarantee = booking.get("guaranteeInfo") or {}
    cancellation = booking.get("cancellation") or {}

    prepaid = _money(guarantee.get("totalPrepaid"))
    penalty = _money(cancellation.get("penaltyAmount"))
    plan = RefundPlan(booking=number, prepaid=prepaid, penalty=penalty)

    if str(booking.get("status") or "").lower() != "cancelled":
        plan.problem = "бронь не отменена"
        return plan
    if prepaid <= 0:
        plan.problem = "предоплаты не было"
        return plan

    plan.amount = max(0, prepaid - penalty)
    if plan.amount == 0:
        plan.problem = "удержано полностью по правилам отмены"
        return plan

    if not payment:
        plan.problem = "платёж по этой броне не найден"
        return plan

    plan.payment_id = str(payment.get("pg_payment_id") or "")
    plan.card = str(payment.get("pg_card_pan") or "")
    plan.already_refunded = _money(payment.get("pg_refund_amount")) + _money(
        payment.get("pg_revoked_amount"))

    if plan.already_refunded > 0:
        # Повторный возврат — это вторая выдача тех же денег. Мягче
        # ошибиться в сторону «не вернули»: это заметят и исправят, а лишний
        # возврат обнаружится при сверке, когда деньги уже ушли.
        plan.problem = f"возврат уже оформлен на {plan.already_refunded}"
        return plan

    оплачено = _money(payment.get("pg_amount"))
    if оплачено and plan.amount > оплачено:
        plan.problem = f"к возврату {plan.amount} больше оплаченного {оплачено}"
    return plan


async def refund_for_booking(settings: Any, booking: dict[str, Any]) -> RefundPlan:
    """Найти платёж по броне и посчитать возврат. Денег не двигает."""
    number = str(booking.get("number") or "")
    plan = RefundPlan(booking=number)
    if not number:
        plan.problem = "нет номера брони"
        return plan

    # Сумму считаем ПЕРВОЙ, до всякого банка: она берётся из данных Exely и
    # не зависит от того, есть ли у нас доступ к платёжной системе. Иначе
    # отель, не вписавший ключи, слышал бы «не настроено» вместо «гостю
    # причитается столько-то» — а вернуть деньги руками он может и без нас.
    plan = plan_refund(booking, {})
    if plan.amount <= 0:
        return plan

    provider = get_provider(settings)
    if provider is None:
        plan.problem = "доступ к банку не настроен (PAYMENT_TERMINAL_ID и ключ)"
        return plan
    if not hasattr(provider, "find_payment"):
        plan.problem = f"поставщик «{provider.name}» не умеет искать платежи"
        return plan

    try:
        # Ищем по номеру брони: Exely пишет его в описание платежа целиком.
        payment = await provider.find_payment(needle=number)
    except PaymentError as error:
        plan.problem = f"платёж не искался: {error}"
        return plan

    return plan_refund(booking, payment)


async def _still_cancelled(settings: Any, number: str) -> bool | None:
    """Отменена ли бронь прямо сейчас. None — проверить не удалось.

    Отдельная проверка перед самой отправкой денег. Exely восстанавливает
    бронь, если гость подтвердил проживание в письме об отмене, и тогда
    возвращать нечего — а расчёт к этому моменту уже сделан.

    Не удалось проверить — возвращаем None, и вызывающий решает сам. Считать
    «наверное, всё ещё отменена» здесь нельзя: цена ошибки — чужие деньги.
    """
    try:
        from .booking_system.exely_api import ExelyApi

        api = ExelyApi(settings.exely_client_id, settings.exely_client_secret,
                       settings.exely_property_id, auth_url=settings.exely_auth_url,
                       api_base=settings.exely_api_base)
        data = await api._get(
            f"/v1/properties/{settings.exely_property_id}/bookings/{number}")
        status = str(((data or {}).get("booking") or {}).get("status") or "")
        return status.lower() == "cancelled" if status else None
    except Exception as error:  # noqa: BLE001
        logger.warning("Статус брони %s не перечитан: %s", number, error)
        return None


async def execute(settings: Any, plan: RefundPlan) -> tuple[bool, str]:
    """Отправить возврат. Возвращает (сделано, что сказать).

    Вызывается только после plan_refund и только если отель включил
    автоматический возврат. Все запреты проверяются здесь ещё раз: между
    расчётом и отправкой может пройти время, а цена ошибки — чужие деньги.
    """
    if not plan.due:
        return False, plan.problem or "возвращать нечего"

    if not bool(getattr(settings, "refund_auto", False)):
        return False, "автоматический возврат выключен"

    limit = int(getattr(settings, "refund_max", 0) or 0)
    if limit and plan.amount > limit:
        # Предел не про недоверие к отелю, а про опечатку в правилах Exely:
        # одна лишняя цифра не должна уходить в банк без человека.
        return False, f"сумма {plan.amount} больше предела {limit} — нужен человек"

    # Бронь могла ожить: гость подтверждает проживание в письме об отмене, и
    # Exely восстанавливает бронирование сам. Между расчётом и отправкой это
    # успевает произойти, а деньги обратно не позовёшь.
    still = await _still_cancelled(settings, plan.booking)
    if still is False:
        return False, "бронь восстановлена — возврат отменён"

    provider = get_provider(settings)
    if provider is None or not hasattr(provider, "refund"):
        return False, "доступ к банку не настроен"
    try:
        result = await provider.refund(payment_id=plan.payment_id, amount_tenge=plan.amount)
    except PaymentError as error:
        logger.warning("Возврат по броне %s не прошёл: %s", plan.booking, error)
        return False, f"банк отказал: {error}"

    logger.info("Возврат по броне %s: %s ₸, платёж %s",
                plan.booking, plan.amount, plan.payment_id)
    return True, str(result.get("message") or "принят банком")


def describe(plan: RefundPlan, done: bool, note: str) -> list[str]:
    """Что написать отелю. Одинаково и для расчёта, и для выполненного возврата."""
    if done:
        заголовок = "Возврат по отменённой броне"
    elif plan.amount > 0:
        заголовок = "Отмена брони: нужен возврат"
    else:
        # Сообщение всё равно нужно: «возвращать нечего» — тоже ответ, и
        # без него бухгалтерия пойдёт считать штраф руками.
        заголовок = "Отмена брони: возврат не требуется"
    lines = [заголовок, "", f"Бронь: {plan.booking}"]
    if plan.prepaid:
        lines.append(f"Оплачено гостем: {plan.prepaid} ₸")
    if plan.penalty:
        lines.append(f"Удержано по правилам отмены: {plan.penalty} ₸")
    if plan.amount:
        lines.append(f"К возврату: {plan.amount} ₸")
    if plan.payment_id:
        lines.append(f"Платёж: {plan.payment_id}"
                     + (f", карта {plan.card}" if plan.card else ""))
    lines.append("")
    if done:
        lines.append(f"Возврат отправлен банком: {note}.")
        lines.append("На карту гостя деньги придут за 1–7 рабочих дней.")
    elif plan.due:
        lines.append(f"Автоматически не отправлен: {note}.")
        lines.append("Оформите возврат в кабинете FreedomPay по номеру платежа выше.")
    else:
        lines.append(f"Возвращать нечего: {note}.")
    return lines
