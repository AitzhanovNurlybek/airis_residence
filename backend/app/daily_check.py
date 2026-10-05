"""
Ежедневная проверка бота — раз в сутки, без участия человека.

Зачем. 4 октября 2026 бот сутки не отвечал гостям: бесплатный тариф Green API
пускал только три чата в месяц. Узнали по жалобе, через сутки, а один из
гостей в это время жил в отеле и ждал ответа. Скрипт проверки был
(`proverka_nomera.py`), но его запускают руками — то есть уже после жалобы.

Что проверяется — то, что ломалось или может сломаться молча:
- WhatsApp-номер привязан, адрес вебхука на месте, входящие и звонки включены;
- за сутки не было упора в лимит тарифа и неушедших ответов гостям;
- справка об отеле грузится с сайта;
- Exely отдаёт наличие;
- перенос броней из Exely не отстал (по нему бот ищет бронь по фамилии);
- ключ модели принимается (подсчёт токенов — бесплатный запрос);
- ключ распознавания голосовых принимается;
- уведомления отелю настроены.

Всё только чтение. Гостям ничего не уходит. При проблемах пишем
разработчику (WhatsApp и Telegram), а планировщик GitHub падает красным —
GitHub присылает письмо. Письмо доходит, даже когда сломан сам WhatsApp.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

GREEN = "https://api.green-api.com/waInstance{id}/{method}/{token}"
ANTHROPIC_COUNT = "https://api.anthropic.com/v1/messages/count_tokens"
ANTHROPIC_MESSAGES = "https://api.anthropic.com/v1/messages"


async def run(settings: Settings, *, booking: Any = None) -> dict[str, Any]:
    """Прогнать проверки. Возвращает {"ok", "problems", "checks"}."""
    problems: list[str] = []
    checks: dict[str, Any] = {}

    def плохо(что: str) -> None:
        problems.append(что)

    async with httpx.AsyncClient(timeout=30) as client:
        await _whatsapp(client, settings, checks, плохо)
        await _model(client, settings, checks, плохо)
        await _speech(client, settings, checks, плохо)

    await _facts(settings, checks, плохо)
    await _exely(settings, booking, checks, плохо)
    await _bookings_fresh(settings, checks, плохо)

    checks["lead_notify_configured"] = bool(settings.lead_notify_numbers)
    if not checks["lead_notify_configured"]:
        плохо("уведомления отелю не настроены (LEAD_NOTIFY_PHONE) — уходят в «сообщение себе»")

    return {"ok": not problems, "problems": problems, "checks": checks}


async def _whatsapp(client: httpx.AsyncClient, settings: Settings,
                    checks: dict[str, Any], плохо) -> None:
    if not (settings.green_api_id and settings.green_api_token):
        плохо("WhatsApp не настроен: нет GREEN_API_ID / GREEN_API_TOKEN")
        return

    def url(method: str) -> str:
        return GREEN.format(id=settings.green_api_id, method=method, token=settings.green_api_token)

    try:
        state = (await client.get(url("getStateInstance"))).json()
        live = (await client.get(url("getSettings"))).json()
        out = (await client.get(url("lastOutgoingMessages"), params={"minutes": 24 * 60})).json()
    except Exception as error:  # noqa: BLE001
        плохо(f"Green API не отвечает: {error}")
        return

    checks["whatsapp_state"] = state.get("stateInstance")
    if state.get("stateInstance") != "authorized":
        плохо(f"WhatsApp-номер не авторизован: «{state.get('stateInstance')}» — нужен QR-код")

    hook = str(live.get("webhookUrl") or "")
    ожидаем = f"{settings.site_url.rstrip('/')}/api/backend/api/webhooks/whatsapp"
    checks["webhook_ok"] = hook.startswith(ожидаем)
    if not checks["webhook_ok"]:
        плохо(f"адрес вебхука сбит: «{hook.split('?')[0] or 'пусто'}» вместо {ожидаем}")
    if str(live.get("incomingWebhook")) != "yes":
        плохо("в Green API выключен приём входящих (incomingWebhook)")
    if str(live.get("incomingCallWebhook")) != "yes":
        плохо("в Green API выключены уведомления о звонках (incomingCallWebhook)")
    if str(live.get("outgoingMessageWebhook")) != "yes":
        плохо("в Green API выключены уведомления об исходящих с телефона "
              "(outgoingMessageWebhook) — бот не видит, что в чате отвечает сотрудник, "
              "и перебивает его")

    свой = str(live.get("wid") or "")
    исходящие = [o for o in out if isinstance(o, dict)] if isinstance(out, list) else []

    def текст(o: dict[str, Any]) -> str:
        return str(o.get("textMessage") or (o.get("extendedTextMessage") or {}).get("text") or "")

    тревоги = [o for o in исходящие if "НЕ УШЁЛ" in текст(o)]
    лимит = [int(o.get("timestamp", 0)) for o in тревоги
             if "466" in текст(o) or "лимит тарифа" in текст(o)]
    checks["undelivered_24h"] = len(тревоги)
    if лимит:
        после = [o for o in исходящие
                 if int(o.get("timestamp", 0)) > max(лимит) and str(o.get("chatId")) != свой
                 and str(o.get("statusMessage")) in ("sent", "delivered", "read")]
        if not после:
            плохо(f"бот упирается в лимит тарифа Green API: {len(лимит)} ответов гостям за сутки "
                  "не ушли — проверьте оплату тарифа Business")
    elif тревоги:
        плохо(f"за сутки {len(тревоги)} ответов гостям не ушли — подробности в тревогах на ресепшне")


НЕТ_ДЕНЕГ = ("кончились деньги на ключе Anthropic — бот отвечает гостям запасной фразой. "
             "Пополните: console.anthropic.com → Plans & Billing")


async def _model(client: httpx.AsyncClient, settings: Settings,
                 checks: dict[str, Any], плохо) -> None:
    if not settings.anthropic_api_key:
        плохо("нет ключа модели (ANTHROPIC_API_KEY) — бот отвечает только запасной фразой")
        return
    try:
        # Подсчёт токенов бесплатный и проверяет сразу и ключ, и имя модели.
        response = await client.post(
            ANTHROPIC_COUNT,
            headers={"x-api-key": settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": settings.concierge_model,
                  "messages": [{"role": "user", "content": "проверка"}]},
        )
    except Exception as error:  # noqa: BLE001
        плохо(f"модель недоступна: {error}")
        return
    checks["model"] = settings.concierge_model
    checks["model_ok"] = response.status_code == 200
    if "credit balance" in response.text.lower():
        плохо(НЕТ_ДЕНЕГ)
        return
    if response.status_code != 200:
        плохо(f"модель {settings.concierge_model} не принимает запрос: "
              f"HTTP {response.status_code} {response.text[:120]}")
        return
    # Подсчёт токенов бесплатный, и не факт, что он всегда смотрит на баланс.
    # 2026-10-05 деньги на ключе кончились, и бот весь день отвечал гостям
    # запасной фразой, — поэтому ещё настоящий запрос на один токен самой
    # дешёвой моделью (баланс общий на организацию): тысячные доли цента.
    try:
        ответ = await client.post(
            ANTHROPIC_MESSAGES,
            headers={"x-api-key": settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5", "max_tokens": 1,
                  "messages": [{"role": "user", "content": "ok"}]},
        )
    except Exception as error:  # noqa: BLE001
        плохо(f"модель недоступна: {error}")
        return
    checks["credits_ok"] = ответ.status_code == 200
    if "credit balance" in ответ.text.lower():
        плохо(НЕТ_ДЕНЕГ)
    elif ответ.status_code != 200:
        плохо(f"модель не отвечает: HTTP {ответ.status_code} {ответ.text[:120]}")


async def _speech(client: httpx.AsyncClient, settings: Settings,
                  checks: dict[str, Any], плохо) -> None:
    ключ = getattr(settings, "speech_api_key", "") or ""
    checks["speech_configured"] = bool(ключ)
    if not ключ:
        плохо("распознавание голосовых выключено: нет SPEECH_API_KEY")
        return
    адрес = (getattr(settings, "speech_api_url", "") or
             "https://api.openai.com/v1/audio/transcriptions")
    модели = адрес.split("/audio/")[0] + "/models"
    try:
        response = await client.get(модели, headers={"Authorization": f"Bearer {ключ}"})
    except Exception as error:  # noqa: BLE001
        плохо(f"служба распознавания не отвечает: {error}")
        return
    checks["speech_ok"] = response.status_code == 200
    if response.status_code != 200:
        плохо(f"ключ распознавания голосовых не принят: HTTP {response.status_code}")


async def _facts(settings: Settings, checks: dict[str, Any], плохо) -> None:
    from .knowledge import KnowledgeUnavailable, load_facts  # noqa: PLC0415

    try:
        facts = await load_facts(settings, force=True)
    except KnowledgeUnavailable as error:
        плохо(f"справка об отеле не грузится с сайта: {error}")
        return
    rooms = facts.get("rooms") or []
    checks["facts_rooms"] = len(rooms)
    if not rooms:
        плохо("в справке об отеле нет номеров — бот не назовёт ни одной цены")


async def _exely(settings: Settings, booking: Any, checks: dict[str, Any], плохо) -> None:
    if booking is None:
        from .booking_system import get_booking_system  # noqa: PLC0415

        booking = get_booking_system(settings)
    from .almaty import today as hotel_today  # noqa: PLC0415

    заезд = hotel_today() + timedelta(days=7)
    started = time.monotonic()
    try:
        result = await booking.availability(заезд, заезд + timedelta(days=1), guests=2)
    except Exception as error:  # noqa: BLE001
        плохо(f"Exely не отдаёт наличие: {error}")
        return
    checks["exely_seconds"] = round(time.monotonic() - started, 1)
    checks["exely_offers"] = len(result.offers)
    if not result.offers:
        плохо("Exely вернул пустое наличие — ни одной категории")


async def _bookings_fresh(settings: Settings, checks: dict[str, Any], плохо) -> None:
    """Свежая ли своя копия броней — по ней бот ищет бронь по фамилии.

    2026-10-05 гость с бронью на сегодня по фамилии не нашёлся: перенос из
    Exely читал одну страницу списка из семи, и свежих броней в копии не было
    уже три дня. Брони в отеле меняются каждый день, поэтому самая свежая
    правка старше двух суток значит, что перенос стоит.
    """
    if not settings.exely_api_ready:
        return
    from sqlalchemy import func, select  # noqa: PLC0415

    from .db import ExelyBooking, SessionLocal  # noqa: PLC0415

    try:
        async with SessionLocal() as session:
            последняя = (await session.execute(select(func.max(ExelyBooking.modified_at)))).scalar()
    except Exception as error:  # noqa: BLE001
        плохо(f"копия броней не читается из базы: {error}")
        return
    checks["bookings_last_modified"] = последняя or ""
    if not последняя:
        плохо("копия броней пуста — бот не найдёт бронь по фамилии (sync-bookings)")
        return
    from datetime import datetime, timezone  # noqa: PLC0415

    try:
        когда = datetime.fromisoformat(str(последняя).replace("Z", "+00:00"))
    except ValueError:
        return
    if когда.tzinfo is None:
        когда = когда.replace(tzinfo=timezone.utc)
    отстала = datetime.now(timezone.utc) - когда
    if отстала > timedelta(days=2):
        плохо(f"перенос броней из Exely стоит {отстала.days} дн. — бот не найдёт свежую "
              "бронь по фамилии; проверь sync-bookings в followup.yml")


def describe(result: dict[str, Any]) -> str:
    """Сообщение разработчику: что сломалось и с чего начать."""
    lines = ["⚠️ Ежедневная проверка бота Airis: есть проблемы", ""]
    lines += [f"• {p}" for p in result.get("problems", [])]
    lines += ["", "Полная проверка: backend\\proverka_nomera.py"]
    return "\n".join(lines)
