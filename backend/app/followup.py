"""
Разговоры, которые оборвались на полпути.

Гость спросил про свободные номера, получил цены — и замолчал. Не отказался,
не забронировал, просто пропал. Консьерж такой разговор не продолжит: он
отвечает на сообщения, а сообщений больше нет. Отель при этом уверен, что
бот «отработал», хотя гость ушёл ни с чем.

Здесь этот разрыв закрывается: спустя пару часов тишины гость получает одно
сообщение, которое возвращает его к тому, на чём остановились.

────────────────────────────────────────────────────────────────────────
ПОЧЕМУ ЭТО СДЕЛАНО ИМЕННО ТАК

**Решает модель, а не таймер.** Тишина после «спасибо, я подумаю» и тишина
после «а сколько стоит Comfort?» — разные вещи. Первую трогать не надо,
вторую надо. Поэтому перед отправкой модель читает разговор и отвечает, есть
ли что дожимать; «нет» — обычный и частый ответ, и он ничего не отправляет.

**Не больше двух раз.** Первое сообщение возвращает к разговору, второе —
прощается и оставляет дверь открытой. Третьего не бывает. Человек, не
ответивший дважды, ответил: WhatsApp считает такую настойчивость спамом и
блокирует номер, а гость — навязчивостью и уходит к конкуренту.

**Любая реплика гостя обнуляет счёт.** Отметки о дожиме считаются только
после последнего сообщения гостя. Написал — значит разговор живой, и в
следующий раз всё начинается заново. Отдельного «сброса» нет: он получается
сам, и забыть про него негде.

**Ночью молчим.** Часы те же, что у остальной рассылки. Сообщение никуда не
денется: отметка ставится при отправке, и утренний запуск подберёт его снова.

**Отметка ставится до отправки.** Если WhatsApp не ответит, гость останется
без сообщения — это неприятно. Если отметка не поставится, он получит его
дважды — это хуже.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .almaty import now as hotel_now
from .channels.whatsapp import WhatsAppChannel, WhatsAppError, for_whatsapp
from .concierge import ANTHROPIC_URL, ANTHROPIC_VERSION
from .db import DialogFollowup, DialogMessage, utcnow
from .knowledge import KnowledgeUnavailable, load_facts, render_brief
from .lifecycle import quiet_hours

logger = logging.getLogger(__name__)

CHANNEL = "whatsapp"

#: Сколько тишины считать обрывом. Два часа — гость успел отвлечься, но ещё
#: помнит, о чём шла речь. Через десять минут писать рано, через сутки поздно.
STALE_HOURS = 2

#: Пауза перед вторым, прощальным сообщением. Сутки: если человек не ответил
#: за день, ещё одно напоминание в тот же вечер только раздражает.
FINAL_HOURS = 24

#: Дальше этого срока разговор считается закрытым и не трогается никогда.
#: Проверено на боевой переписке: без этого предела дожим предложил вернуться
#: к разговору про даты «1–10 мая» — при том что май давно прошёл. Гость,
#: молчавший три дня, передумал или уже съездил; напоминание тут выглядит не
#: заботой, а рассылкой.
MAX_AGE_HOURS = 72

#: Больше двух не пишем никогда.
MAX_STEPS = 2

#: Сколько разговоров разбирать за запуск. Каждый — обращение к модели, а
#: запуск живёт ограниченное время.
BATCH = 20

#: Сколько последних реплик показывать модели. Решение принимается по концовке
#: разговора, а не по всей его истории.
DEPTH = 12


@dataclass
class Nudge:
    """Одно готовое сообщение вдогонку."""

    chat_id: str
    text: str
    step: int
    reason: str


DECIDE_PROMPT = """Ты помогаешь отелю не терять гостей, которые написали и пропали.

Ниже — переписка гостя с консьержем отеля. Последним говорил консьерж, гость не ответил {hours} часов.

Реши, стоит ли написать гостю ещё раз, и если да — составь это сообщение.

ПИСАТЬ СТОИТ, когда разговор оборвался на полпути и гость остался без решения:
— спрашивал про свободные номера или цены и не ответил, берёт ли;
— выбирал между категориями и не выбрал;
— собирался бронировать и не дошёл до формы;
— задал вопрос, получил ответ и замолчал, не сказав, подходит ли.

ПИСАТЬ НЕ НАДО, когда:
— гость отказался, сказал «спасибо, не надо», «я подумаю», «позже напишу» — он уже ответил;
— гость забронировал или сказал, что бронирует сам;
— разговор был про мелочь и закончен: узнал время заезда, адрес, есть ли парковка;
— гость злится или жалуется — тут нужен человек, а не напоминание;
— консьерж последним задал вопрос, ответ на который ничего не решает.

КАКИМ ДОЛЖНО БЫТЬ СООБЩЕНИЕ (если пишем)
— Одно-два предложения. Это напоминание, а не новое письмо.
— Начни с того, на чём остановились, конкретно: даты, категория, цена. «Вы ещё с нами?» — пустое сообщение, оно раздражает.
— Закончи вопросом, на который есть ответ «да» или «нет». Гостю должно быть легко закрыть разговор в любую сторону.
— Не дави и не торопи. Никаких «последний номер», «цена вырастет», «только сегодня», если этого не было в разговоре.
— Ничего не говори о наличии В НАСТОЯЩЕМ ВРЕМЕНИ. Ни «зарезервирован», ни «отложен», ни «пока свободен», ни «всё ещё доступен», ни «номер за вами» — никакими словами. Отель ничего не держит до оформления, шахматку ты сейчас не видишь, и за прошедшие часы номер могли занять. Гость поверит и приедет ни с чем.
— О наличии и ценах говори только в прошедшем времени, как о том, что прозвучало в разговоре: «мы смотрели Standart на 2–3 сентября за 36 000 ₸». Это правда в любом случае, а «свободен» — только пока не занят.
— Если хочешь подтолкнуть к брони, зови проверить заново: «посмотреть, свободно ли ещё?» Это и честно, и возвращает гостя в разговор.
— Не здоровайся заново: вы уже разговариваете.

{final_note}

Ответь строго JSON без пояснений:
{{"write": true/false, "why": "коротко, почему", "text": "сообщение гостю или пустая строка"}}"""

FINAL_NOTE = """ЭТО ВТОРОЕ И ПОСЛЕДНЕЕ СООБЩЕНИЕ. Первое гость уже получил и не ответил.
Поэтому: попрощайся, оставь дверь открытой и прямо скажи, что больше не побеспокоишь. Не повторяй первое сообщение и не задавай новых вопросов по существу."""


def _who(chat_id: str) -> str:
    """Как назвать чат в логе и отчёте.

    Целиком номер в логи не пишем, а хвост строки бесполезен: у
    «77054004448@c.us» последние шесть символов — «0@c.us». Берём последние
    цифры самого номера.
    """
    digits = "".join(ch for ch in str(chat_id) if ch.isdigit())
    return f"…{digits[-4:]}" if digits else str(chat_id)[:8]


def _text_of(content: str) -> str:
    """Реплика в читаемом виде.

    В историю кладутся и вызовы инструментов — списком в JSON. Для решения
    они не нужны: важно, что консьерж в итоге сказал гостю.
    """
    raw = (content or "").strip()
    if not raw.startswith("[") and not raw.startswith("{"):
        return raw
    try:
        parsed = json.loads(raw)
    except ValueError:
        return raw
    if isinstance(parsed, list):
        parts = [str(b.get("text") or "") for b in parsed
                 if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(p for p in parts if p).strip()
    return ""


async def _stale_chats(session: AsyncSession, limit: int = BATCH,
                       stale_hours: int = STALE_HOURS,
                       since: Any = None) -> list[tuple[str, int]]:
    """Разговоры, где консьерж сказал последнее слово и наступила тишина.

    `since` отсекает всё, что началось раньше назначенного момента. Это не
    тонкость, а защита от единственного по-настоящему опасного сценария:
    в базе лежат прошлые переписки, и первый же запуск без границы написал
    бы всем сразу — тестовым чатам, разговорам месячной давности, людям,
    давно всё решившим. Одна аккуратная функция мгновенно стала бы
    рассылкой, а номер отеля — заблокированным.

    Возвращает пары «чат, сколько часов молчит».
    """
    latest = (
        select(
            DialogMessage.chat_id.label("chat_id"),
            func.max(DialogMessage.id).label("last_id"),
        )
        .where(DialogMessage.channel == CHANNEL)
        .group_by(DialogMessage.chat_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(DialogMessage.chat_id, DialogMessage.role, DialogMessage.created_at)
            .join(latest, DialogMessage.id == latest.c.last_id)
        )
    ).all()

    border = utcnow()
    out: list[tuple[str, int]] = []
    for chat_id, role, when in rows:
        if role != "assistant" or when is None:
            continue
        said = when if when.tzinfo else when.replace(tzinfo=border.tzinfo)
        if since is not None and said < since:
            continue
        hours = int((border - said).total_seconds() // 3600)
        if stale_hours <= hours <= MAX_AGE_HOURS:
            out.append((str(chat_id), hours))
    out.sort(key=lambda pair: pair[1])
    return out[:limit]


async def _step_for(session: AsyncSession, chat_id: str,
                    final_hours: int = FINAL_HOURS) -> int | None:
    """Какое по счёту сообщение вдогонку сейчас уместно.

    Считаются только отметки после последней реплики гостя: написал — значит
    разговор живой, и счёт начинается заново. Возвращает None, если писать
    не время или уже нельзя.
    """
    spoke = (
        await session.execute(
            select(func.max(DialogMessage.created_at))
            .where(DialogMessage.channel == CHANNEL)
            .where(DialogMessage.chat_id == chat_id)
            .where(DialogMessage.role == "user")
        )
    ).scalar_one_or_none()
    if spoke is None:
        return None

    done = (
        await session.execute(
            select(DialogFollowup)
            .where(DialogFollowup.channel == CHANNEL)
            .where(DialogFollowup.chat_id == chat_id)
            .where(DialogFollowup.sent_at > spoke)
            .order_by(DialogFollowup.sent_at.desc())
        )
    ).scalars().all()

    if len(done) >= MAX_STEPS:
        return None
    if not done:
        return 1

    last = done[0].sent_at
    border = utcnow()
    sent = last if last.tzinfo else last.replace(tzinfo=border.tzinfo)
    if border - sent < timedelta(hours=final_hours):
        return None
    return len(done) + 1


async def _history(session: AsyncSession, chat_id: str) -> list[dict[str, str]]:
    rows = (
        await session.execute(
            select(DialogMessage)
            .where(DialogMessage.channel == CHANNEL)
            .where(DialogMessage.chat_id == chat_id)
            .order_by(DialogMessage.id.desc())
            .limit(DEPTH)
        )
    ).scalars().all()

    out: list[dict[str, str]] = []
    for row in reversed(rows):
        said = _text_of(row.content)
        if said:
            out.append({"role": "Гость" if row.role == "user" else "Консьерж", "text": said})
    return out


async def _decide(settings: Any, talk: list[dict[str, str]], hours: int,
                  step: int, brief: str) -> tuple[bool, str, str]:
    """Спросить модель, дожимать ли этот разговор. Возвращает (писать, почему, текст)."""
    if not settings.anthropic_api_key:
        return False, "нет ключа Anthropic", ""

    lines = "\n".join(f"{m['role']}: {m['text']}" for m in talk)
    system = DECIDE_PROMPT.format(
        hours=hours, final_note=FINAL_NOTE if step >= MAX_STEPS else ""
    )
    body = {
        "model": settings.concierge_model,
        "max_tokens": 700,
        "system": system,
        "messages": [{
            "role": "user",
            "content": f"СПРАВКА ОБ ОТЕЛЕ (для цен и фактов):\n{brief}\n\nПЕРЕПИСКА:\n{lines}",
        }],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            answer = await client.post(ANTHROPIC_URL, json=body, headers=headers)
            if answer.status_code >= 400:
                logger.warning("Решение о дожиме: HTTP %s", answer.status_code)
                return False, f"модель ответила {answer.status_code}", ""
            payload = answer.json()
    except Exception as error:  # noqa: BLE001 — сбой не повод писать гостю наугад
        logger.warning("Решение о дожиме не получено: %s", type(error).__name__)
        return False, f"модель недоступна: {error}", ""

    said = "".join(
        block.get("text", "") for block in payload.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
    # Модель охотно оборачивает JSON в ```json — вырезаем, но не гадаем
    # дальше: неразобранный ответ означает «не писать», а не «написать что-то».
    if said.startswith("```"):
        said = said.strip("`")
        said = said[4:] if said.lower().startswith("json") else said
    try:
        verdict = json.loads(said[said.index("{"):said.rindex("}") + 1])
    except (ValueError, KeyError):
        logger.warning("Решение о дожиме не разобрано: %s", said[:120])
        return False, "ответ модели не разобран", ""

    write = bool(verdict.get("write"))
    text = str(verdict.get("text") or "").strip()
    why = str(verdict.get("why") or "").strip()
    if write and not text:
        return False, "модель согласилась писать, но текста не дала", ""
    return write, why, text


async def plan(session: AsyncSession, settings: Any) -> list[Nudge]:
    """Собрать сообщения вдогонку по оборванным разговорам."""
    since = settings.followup_from
    if since is None:
        # Пустая настройка — не «дожимать всех подряд», а «не дожимать».
        # Рассылка гостям не должна включаться сама собой от выкладки кода.
        logger.info("Дожим выключен: FOLLOWUP_SINCE не задан")
        return []

    stale_hours = max(1, int(getattr(settings, "followup_after_hours", STALE_HOURS)))
    final_hours = max(1, int(getattr(settings, "followup_final_hours", FINAL_HOURS)))

    try:
        brief = render_brief(await load_facts(settings))
    except KnowledgeUnavailable as error:
        logger.warning("Дожим без справки не делаем: %s", error)
        return []

    out: list[Nudge] = []
    for chat_id, hours in await _stale_chats(session, stale_hours=stale_hours, since=since):
        step = await _step_for(session, chat_id, final_hours=final_hours)
        if step is None:
            continue
        talk = await _history(session, chat_id)
        if not talk:
            continue
        write, why, text = await _decide(settings, talk, hours, step, brief)
        if not write:
            logger.info("Дожим %s: не пишем — %s", _who(chat_id), why or "разговор закончен")
            continue
        out.append(Nudge(chat_id=chat_id, text=text, step=step, reason=why))
    return out


async def run(session: AsyncSession, settings: Any, *, dry_run: bool = False) -> dict[str, Any]:
    """Найти оборванные разговоры и написать по ним. Дёргается планировщиком."""
    if quiet_hours() and not dry_run:
        return {"sent": 0, "note": "ночь", "hour": hotel_now().hour}

    nudges = await plan(session, settings)

    if dry_run:
        return {
            "dry_run": True,
            "hour": hotel_now().hour,
            "since": str(settings.followup_from or "не задан — дожим выключен"),
            "planned": [{"chat": _who(n.chat_id), "step": n.step,
                         "why": n.reason, "text": n.text} for n in nudges],
        }
    if not nudges:
        return {"sent": 0, "note": "оборванных разговоров нет"}

    try:
        channel = WhatsAppChannel(settings.green_api_id, settings.green_api_token)
    except WhatsAppError as error:
        logger.warning("Дожим невозможен: %s", error)
        return {"sent": 0, "error": str(error)}

    sent = 0
    for nudge in nudges:
        # Отметка ДО отправки: повтор хуже пропуска.
        session.add(DialogFollowup(channel=CHANNEL, chat_id=nudge.chat_id, step=nudge.step))
        await session.commit()
        try:
            await channel.send(nudge.chat_id, for_whatsapp(nudge.text))
            sent += 1
            logger.info("Дожим %s (шаг %d): %s", _who(nudge.chat_id), nudge.step, nudge.reason)
        except WhatsAppError as error:
            logger.warning("Дожим не ушёл: %s", error)
            continue

        # Записываем в историю разговора наравне с обычным ответом.
        #
        # Иначе получается разговор, где консьерж не помнит собственных слов:
        # гость отвечает «на троих» на вопрос из дожима, а в истории этого
        # вопроса нет — и консьерж переспрашивает то, что сам же спросил час
        # назад. Для гостя это выглядит так, будто его не читают.
        session.add(DialogMessage(channel=CHANNEL, chat_id=nudge.chat_id,
                                  role="assistant", content=nudge.text))
        await session.commit()

    return {"sent": sent, "planned": len(nudges)}
