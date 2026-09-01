"""
Приём уведомлений о платежах от банка.

Зачем это вообще существует. Чтобы вернуть деньги при отмене брони, нужно
знать номер платежа. Своего платежа мы не создаём — гостя на страницу банка
отправляет модуль Exely, — и найти платёж по номеру брони через API нельзя:
поддержка FreedomPay ответила прямо, что «такого API нет», фильтры есть
только в кабинете.

Зато они же сказали главное: «по каждому платежу мы отправляем коллбэки на
url, указанный в параметре pg_result_url». А в уведомлении приходит
`pg_description` — и туда Exely записывает номер брони целиком:

    Airis Residence Hotel. 20260901-509506-1262595670. Нурлыбек Айтжанов…

Отсюда весь замысел: ловить уведомления и запоминать номер платежа рядом с
описанием. Тогда при отмене нужный платёж находится у себя в базе, и поиска,
которого нет у банка, не требуется вовсе.

────────────────────────────────────────────────────────────────────────
ЧТО ТРЕБУЕТ БАНК ОТ ЭТОГО АДРЕСА

Дословно из их ответа и документации:

**Общедоступность.** «Адрес Result URL на стороне мерчанта должен быть
общедоступным и не требовать авторизации». Поэтому здесь нет проверки
секрета, как у остальных наших вебхуков, — вместо неё подпись.

**Ответ 200 и XML.** Банк ждёт `pg_status`, `pg_description`, `pg_salt` и
`pg_sig`. Ответить «ok» текстом недостаточно.

**Адрес без параметров.** «Рекомендуется указывать pg_result_url без
query-параметров»; вызов приходит только на основной адрес.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ ПОДПИСЬ ОБЯЗАТЕЛЬНА

Адрес открыт интернету и не требует авторизации — так велит банк. Без
проверки подписи любой желающий мог бы прислать сюда выдуманный платёж, и
мы бы запомнили чужой номер, а потом вернули по нему деньги.

Подпись считается тем же способом, что у запросов, только имя скрипта —
последняя часть нашего адреса, а не `init_payment.php`.
"""

from __future__ import annotations

import hashlib
import logging
import secrets as _secrets

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .db import SeenPayment, get_session
from .payments import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["платежи"])


def _money(value: object) -> int:
    try:
        return int(round(float(str(value).replace(",", "."))))
    except (TypeError, ValueError):
        return 0


def _answer(settings: Settings, status: str, note: str) -> str:
    """Ответ банку. Он ждёт XML с подписью, а не слово «ok»."""
    salt = _secrets.token_hex(8)
    fields = {"pg_status": status, "pg_description": note, "pg_salt": salt}
    script = settings.payment_result_url.rstrip("/").rsplit("/", 1)[-1]
    parts = [script] + [str(fields[k]) for k in sorted(fields)] + [
        settings.payment_client_secret]
    sig = hashlib.md5(";".join(parts).encode("utf-8")).hexdigest()
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f"<response><pg_status>{status}</pg_status>"
        f"<pg_description>{note}</pg_description>"
        f"<pg_salt>{salt}</pg_salt><pg_sig>{sig}</pg_sig></response>"
    )


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


@router.post("/result")
async def payment_result(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Уведомление банка о платеже: запоминаем номер платежа и описание.

    Отвечаем 200 и XML во всех случаях, кроме неверной подписи. Банк на
    другой ответ начнёт слать повторы, а повторять здесь нечего: мы ничего
    не проводим, только записываем.
    """
    form = await request.form()
    payload = {k: str(v) for k, v in form.items()}

    provider = get_provider(settings)
    if provider is None:
        # Ключей нет — проверить подпись нечем, а верить на слово нельзя.
        logger.warning("Уведомление о платеже пришло, но доступ к банку не настроен")
        return _xml(_answer(settings, "error", "not configured"))

    if not provider.verify_callback(payload, dict(request.headers)):
        # Адрес открыт интернету и не требует авторизации — так велит банк.
        # Единственная защита здесь — подпись, и пропускать неподписанное
        # значит позволить кому угодно объявить платёж существующим.
        logger.warning("Уведомление о платеже с неверной подписью — отброшено")
        return _xml(_answer(settings, "error", "bad signature"))

    payment_id = str(payload.get("pg_payment_id") or "").strip()
    if not payment_id:
        return _xml(_answer(settings, "ok", "no payment id"))

    _, status = provider.parse_callback(payload)

    record = await session.get(SeenPayment, payment_id)
    if record is None:
        record = SeenPayment(payment_id=payment_id)
        session.add(record)
    record.order_id = str(payload.get("pg_order_id") or "")[:60]
    record.description = str(payload.get("pg_description") or "")[:400]
    record.amount = _money(payload.get("pg_amount"))
    record.currency = str(payload.get("pg_currency") or "KZT")[:8]
    record.status = status
    record.card = str(payload.get("pg_card_pan") or "")[:40]
    await session.commit()

    logger.info("Платёж %s (%s) запомнен: %s", payment_id, status,
                record.description[:60])
    return _xml(_answer(settings, "ok", "accepted"))
