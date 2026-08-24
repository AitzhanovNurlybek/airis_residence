"""
Разбор платёжных документов: PDF и фото квитанций.

Гость присылает в переписку платёжку — скан поручения, чек из банковского
приложения, фото квитанции. Задача: понять, кто заплатил, сколько и за что, и
свести это с бронью.

Здесь два разных действия, и их важно не путать.

**Прочитать** документ — работа модели: форматов квитанций столько же, сколько
банков, и разбирать их правилами бессмысленно.

**Решить, что это оплата брони** — работа кода. Модель возвращает только то,
что написано в бумаге; сверку с базой, проверку суммы и отметку об оплате
делает сервер. Иначе достаточно прислать красиво оформленный документ с
нужным текстом, чтобы номер оказался оплаченным.

Отсюда же правило про уверенность: если номер брони в платёжке не назван, а
подобрать по сумме и имени однозначно не вышло, документ уходит менеджеру.
Ошибиться в пользу гостя здесь дороже, чем задержать заселение на час.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from .booking_system import BookingSystem
from .concierge import ANTHROPIC_URL, ANTHROPIC_VERSION
from .config import Settings
from .almaty import today as hotel_today

#: Больше — почти наверняка не платёжка, а что-то присланное по ошибке.
MAX_DOC_MB = 8

EXTRACT_PROMPT = """Перед тобой платёжный документ: банковское поручение, чек, квитанция или скриншот перевода.

Извлеки только то, что действительно написано в документе. Ничего не додумывай:
поля, которых в бумаге нет, оставь пустыми. Лучше пусто, чем догадка — по этим
данным отель отметит номер оплаченным.

Отдельно посмотри на документ как на изображение и поищи следы ПРАВКИ:
разные шрифты или кегли внутри одного поля, цифра, съехавшая с базовой линии
соседних, пятна ретуши и другой фон вокруг суммы или даты, обрезанные края
символов, повторная съёмка экрана с экрана.

Не считай признаком подделки простоту оформления. Отсутствие печати, подписи,
логотипа, БИК, банка или суммы прописью — это не подделка: чеки из мобильных
приложений и выгрузки в PDF часто выглядят именно так. Пиши в red_flags только
то, что указывает на изменение документа, а не на его бедность.

Дату не оценивай вовсе: сегодняшнее число тебе неизвестно, его проверит
система отдельно.

Верни строго JSON без пояснений и без markdown-обрамления:
{
  "is_payment": true|false,        // это вообще платёжный документ?
  "payer": "",                     // кто платит: ФИО или название организации
  "payer_bin": "",                 // БИН/ИИН плательщика, если указан
  "payee": "",                     // КОМУ платят: получатель
  "payee_bin": "",                 // БИН получателя
  "payee_account": "",             // счёт/ИИК получателя
  "amount": 0,                     // сумма в тенге, только число, без пробелов
  "amount_in_words": "",           // сумма прописью, если написана
  "currency": "KZT",
  "paid_at": "",                   // дата платежа ГГГГ-ММ-ДД
  "purpose": "",                   // назначение платежа целиком, как написано
  "reference": "",                 // номер брони или счёта из назначения (L-0001, K-0001, №...)
  "bank": "",                      // банк, если виден
  "doc_number": "",                // номер документа/квитанции
  "status_words": "",              // слова о статусе: «исполнено», «в обработке», «отклонено»
  "red_flags": [],                 // список подозрительных признаков, каждый одной строкой
  "looks_edited": false            // есть ли следы правки изображения
}"""


@dataclass
class PaymentDoc:
    """Что прочитано в документе."""

    is_payment: bool = False
    payer: str = ""
    payer_bin: str = ""
    payee: str = ""
    payee_bin: str = ""
    payee_account: str = ""
    amount: int = 0
    amount_in_words: str = ""
    currency: str = "KZT"
    paid_at: str = ""
    purpose: str = ""
    reference: str = ""
    bank: str = ""
    doc_number: str = ""
    status_words: str = ""
    red_flags: list[str] = field(default_factory=list)
    looks_edited: bool = False
    #: SHA-256 присланного файла — по нему узнаём повторную пересылку.
    doc_hash: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchResult:
    """Что сервер решил делать с прочитанным."""

    #: applied — оплата отмечена; review — нужен человек; rejected — не платёжка.
    verdict: str
    reason: str
    doc: PaymentDoc
    booking_ref: str = ""
    applied_amount: int = 0
    candidates: list[str] = field(default_factory=list)


def _media_type(filename: str) -> str:
    low = filename.lower()
    if low.endswith(".pdf"):
        return "application/pdf"
    if low.endswith(".png"):
        return "image/png"
    if low.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if low.endswith(".webp"):
        return "image/webp"
    return ""


async def read_document(settings: Settings, data: bytes, filename: str) -> PaymentDoc:
    """Отдать документ модели и получить поля. Ничего не решает."""
    media = _media_type(filename)
    if not media:
        raise ValueError("Понимаю только PDF, PNG, JPG и WEBP")
    if len(data) > MAX_DOC_MB * 1024 * 1024:
        raise ValueError(f"Файл больше {MAX_DOC_MB} МБ — вряд ли это квитанция")
    if not settings.anthropic_api_key:
        raise ValueError("Ключ Anthropic не задан — читать документ нечем")

    encoded = base64.standard_b64encode(data).decode("ascii")
    block_type = "document" if media == "application/pdf" else "image"

    payload = {
        "model": settings.concierge_model,
        "max_tokens": 1200,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": block_type,
                        "source": {"type": "base64", "media_type": media, "data": encoded},
                    },
                    {
                        "type": "text",
                        "text": f"Сегодня {hotel_today().isoformat()}.\n\n{EXTRACT_PROMPT}",
                    },
                ],
            }
        ],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
        response.raise_for_status()
        answer = response.json()

    text = "".join(
        block.get("text", "") for block in answer.get("content", []) if block.get("type") == "text"
    ).strip()

    parsed = _parse_json(text)
    return PaymentDoc(
        doc_hash=hashlib.sha256(data).hexdigest(),
        is_payment=bool(parsed.get("is_payment")),
        payer=str(parsed.get("payer") or "").strip(),
        payer_bin=str(parsed.get("payer_bin") or "").strip(),
        payee=str(parsed.get("payee") or "").strip(),
        payee_bin=str(parsed.get("payee_bin") or "").strip(),
        payee_account=str(parsed.get("payee_account") or "").strip(),
        amount=_to_int(parsed.get("amount")),
        amount_in_words=str(parsed.get("amount_in_words") or "").strip(),
        currency=str(parsed.get("currency") or "KZT").strip().upper(),
        paid_at=str(parsed.get("paid_at") or "").strip(),
        purpose=str(parsed.get("purpose") or "").strip(),
        reference=str(parsed.get("reference") or "").strip(),
        bank=str(parsed.get("bank") or "").strip(),
        doc_number=str(parsed.get("doc_number") or "").strip(),
        status_words=str(parsed.get("status_words") or "").strip(),
        red_flags=[str(f).strip() for f in (parsed.get("red_flags") or []) if str(f).strip()],
        looks_edited=bool(parsed.get("looks_edited")),
        raw=parsed,
    )


def _parse_json(text: str) -> dict[str, Any]:
    import json

    cleaned = text.strip()
    # Модель иногда оборачивает ответ в ```json несмотря на просьбу.
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    try:
        return json.loads(cleaned)
    except Exception:  # noqa: BLE001
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except Exception:  # noqa: BLE001
                pass
    return {}


def _to_int(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    digits = "".join(c for c in str(value or "") if c.isdigit())
    return int(digits) if digits else 0


def _digits(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


def check_recipient(doc: PaymentDoc, facts: dict[str, Any] | None) -> tuple[str, str]:
    """
    Деньги вообще нам?

    Самая полезная проверка из всех и единственная по-настоящему надёжная.
    Подделать вид документа несложно, а вот платёж в пользу другой компании
    отелю не поможет никак: сколько бы правдоподобно он ни выглядел, на счёт
    ничего не придёт.

    Сверяем по БИН и по счёту — по двум, потому что в чеках из приложений
    счёт часто скрыт звёздочками, а в скриншотах переводов нет и БИН.
    Возвращаем ('ok'|'mismatch'|'unknown', пояснение).
    """
    legal = ((facts or {}).get("hotel") or {}).get("legal") or {}
    our_bin = _digits(str(legal.get("bin") or ""))
    our_iik = str(legal.get("iik") or "").upper().replace(" ", "")
    our_name = str((facts or {}).get("hotel", {}).get("legalName") or "")

    doc_bin = _digits(doc.payee_bin)
    doc_acc = doc.payee_account.upper().replace(" ", "")

    if our_bin and doc_bin:
        if doc_bin == our_bin:
            return "ok", f"БИН получателя совпал с {our_name}"
        return "mismatch", f"Платёж в пользу БИН {doc.payee_bin}, а у отеля {legal.get('bin')}"

    if our_iik and doc_acc and doc_acc.replace("*", "").isalnum():
        # Звёздочки в середине счёта — обычное дело: сравниваем хвост.
        tail = doc_acc.replace("*", "")[-6:]
        if tail and tail in our_iik:
            return "ok", "Счёт получателя сходится с реквизитами отеля"
        if len(tail) >= 4:
            return "mismatch", f"Счёт получателя {doc.payee_account} не похож на счёт отеля"

    if doc.payee and our_name:
        # Последняя зацепка — имя. Ненадёжна: в чеках оно бывает сокращено
        # до «INCOME HOUSE» или искажено транслитерацией, поэтому сравниваем
        # по опорному слову, а несовпадение считаем «не знаю», не «чужой».
        key = "INCOME HOUSE"
        if key.casefold() in doc.payee.casefold():
            return "ok", "Название получателя совпадает"
        return "unknown", f"Получатель указан как «{doc.payee}» — сверьте вручную"

    return "unknown", "В документе не разобрать, кому ушли деньги"


REJECTING_WORDS = ("отклон", "не исполн", "отмен", "ошибк", "reject", "fail")


async def match_and_apply(
    booking: BookingSystem,
    doc: PaymentDoc,
    *,
    facts: dict[str, Any] | None = None,
    auto_apply: bool = True,
) -> MatchResult:
    """
    Свести платёжку с бронью и, если всё сошлось, отметить оплату.

    Отмечаем сами только при однозначном совпадении: номер брони назван прямо,
    бронь существует и действует, сумма не больше начисленной. Всё остальное —
    менеджеру. Автоматика, которая «почти угадала», в деньгах хуже ручной
    работы.
    """
    if not doc.is_payment:
        return MatchResult("rejected", "Это не платёжный документ", doc)

    if doc.currency not in ("KZT", "", "ТЕНГЕ"):
        return MatchResult("review", f"Валюта {doc.currency}, а не тенге", doc)

    # Деньги ушли не нам — дальше можно не смотреть. Это единственная по-
    # настоящему надёжная проверка: подделать вид документа несложно, а вот
    # платёж чужой компании отелю не поможет ничем.
    recipient, why = check_recipient(doc, facts)
    if recipient == "mismatch":
        return MatchResult("rejected", f"Платёж не отелю. {why}", doc)

    # Дальше — проверки, которые считает код, а не модель.
    #
    # Впечатления модели (`red_flags`) сюда не входят намеренно. Первая версия
    # блокировала оплату по любому её замечанию, и она браковала всё подряд:
    # «нет печати», «нет БИК», «похоже на простой текст». Чеки из мобильных
    # приложений выглядят именно так, и порог оказался невыполнимым.
    #
    # Заявление о правке (`looks_edited`) — другое дело: это утверждение об
    # изменении документа, и по такому оплату не отмечают.
    if doc.looks_edited:
        signs = "; ".join(doc.red_flags) or "изображение выглядит отредактированным"
        return MatchResult("review", f"Следы правки: {signs}", doc)

    # Сумма прописью против цифр: расхождение — классический след правки
    # цифры в отсканированном поручении. Считает код: сравнение чисел моделью
    # не поручают.
    words_mismatch = _words_disagree(doc)
    if words_mismatch:
        return MatchResult("review", words_mismatch, doc)

    stale = _date_problem(doc)
    if stale:
        return MatchResult("review", stale, doc)

    if any(word in doc.status_words.lower() for word in REJECTING_WORDS):
        return MatchResult("review", f"В документе статус «{doc.status_words}»", doc)

    if doc.amount <= 0:
        return MatchResult("review", "Сумма не прочиталась", doc)

    ref = _find_ref(doc)
    if not ref:
        return MatchResult(
            "review",
            "В назначении платежа нет номера брони — сопоставить не с чем",
            doc,
        )

    if not hasattr(booking, "get_booking"):
        return MatchResult("review", "Система бронирования не умеет искать брони", doc, ref)

    found = await booking.get_booking(ref)
    if found is None:
        return MatchResult("review", f"Брони {ref} нет в системе", doc, ref)
    if found.status != "booked":
        return MatchResult("review", f"Бронь {ref} уже {found.status}", doc, ref)

    if found.total_amount and doc.amount > found.total_amount:
        # Переплату не глотаем молча: возможно, платёж относится к нескольким
        # броням или в документе другая сделка.
        return MatchResult(
            "review",
            f"В платёжке {doc.amount}, а по брони начислено {found.total_amount}",
            doc,
            ref,
        )

    # Повторная пересылка. В переписке это обычное дело: «вы получили?»,
    # «на всякий случай ещё раз». Без этой проверки каждая пересылка
    # добавляла бы оплату заново.
    if hasattr(booking, "seen_payment") and await booking.seen_payment(
        ref, doc_hash=doc.doc_hash, doc_number=doc.doc_number, amount=doc.amount
    ):
        return MatchResult(
            "duplicate", f"Этот платёж уже принят по брони {ref}", doc, ref
        )

    # Потолок по сумме — сеть безопасности на случай, если проверка повтора
    # не сработала: два разных документа на одну бронь всё равно не должны
    # переплатить.
    invoices = await booking.invoices(external_id=ref) if hasattr(booking, "invoices") else []
    already = invoices[0].paid_amount if invoices else 0
    if found.total_amount and already + doc.amount > found.total_amount:
        return MatchResult(
            "review",
            f"По брони уже оплачено {already}, ещё {doc.amount} — это больше "
            f"начисленных {found.total_amount}",
            doc,
            ref,
        )

    if not auto_apply or not hasattr(booking, "mark_paid"):
        return MatchResult("review", "Совпадение найдено, но отметка выключена", doc, ref)

    note = f"оплата {doc.amount} ₸ от {doc.payer or 'плательщика'} ({doc.doc_number or 'без номера'})"
    await booking.mark_paid(
        ref, doc.amount, note,
        doc_hash=doc.doc_hash, doc_number=doc.doc_number, payer=doc.payer,
    )
    return MatchResult("applied", "Оплата отмечена", doc, ref, doc.amount)


NUMERALS = {
    "ноль": 0, "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
    "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40,
    "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80,
    "девяносто": 90, "сто": 100, "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800,
    "девятьсот": 900,
}


def _words_to_number(text: str) -> int | None:
    """
    Грубый разбор суммы прописью.

    Полноценный парсер русских числительных здесь не нужен и вреден: он даёт
    ложную уверенность на редких формах. Задача скромнее — поймать случай,
    когда в цифрах сто тысяч, а прописью пятьдесят. Не разобрали — молчим.
    """
    low = text.casefold().replace("-", " ")
    words = [w.strip(".,") for w in low.split()]
    if not words:
        return None

    total = 0
    chunk = 0
    seen = False
    for word in words:
        if word in NUMERALS:
            chunk += NUMERALS[word]
            seen = True
        elif word.startswith("тысяч"):
            total += (chunk or 1) * 1000
            chunk = 0
            seen = True
        elif word.startswith("миллион"):
            total += (chunk or 1) * 1_000_000
            chunk = 0
            seen = True
        elif word.startswith(("тенге", "тг", "kzt")):
            break
    return (total + chunk) if seen else None


SCALE_WORDS = ("тысяч", "миллион", "млн", "тыс")


def _words_disagree(doc: PaymentDoc) -> str:
    if not doc.amount_in_words or not doc.amount:
        return ""
    spelled = _words_to_number(doc.amount_in_words)
    if spelled is None or spelled == 0:
        return ""

    # Разговорные формы («девяносто тыщ») разбираются наполовину: числительное
    # узнаётся, а множитель — нет, и выходит 90 против 90 000. Обвинять
    # документ в подделке из-за просторечия нельзя, поэтому без узнанного
    # множителя молчим: пусть лучше проверка не сработает, чем сработает зря.
    low = doc.amount_in_words.casefold()
    scale_seen = any(word in low for word in SCALE_WORDS)
    if doc.amount >= 1000 and not scale_seen:
        return ""
    if spelled != doc.amount:
        return (
            f"Сумма цифрами {doc.amount}, а прописью «{doc.amount_in_words}» "
            f"читается как {spelled}"
        )
    return ""


def _date_problem(doc: PaymentDoc) -> str:
    if not doc.paid_at:
        return ""
    try:
        when = date.fromisoformat(doc.paid_at)
    except ValueError:
        return ""
    today = hotel_today()
    if when > today:
        return f"Дата платежа {doc.paid_at} — в будущем"
    if (today - when).days > 180:
        return f"Платёж от {doc.paid_at} — старше полугода, вряд ли по этой брони"
    return ""


def _find_ref(doc: PaymentDoc) -> str:
    """Номер брони из назначения платежа."""
    import re

    haystack = f"{doc.reference} {doc.purpose} {doc.doc_number}".upper()
    found = re.search(r"\b([LK])[\s-]?(\d{3,6})\b", haystack)
    if not found:
        return ""
    return f"{found.group(1)}-{int(found.group(2)):04d}"


def describe(result: MatchResult) -> str:
    """Человеческое описание для менеджера и для лога."""
    doc = result.doc
    head = {
        "applied": f"Оплата отмечена по брони {result.booking_ref}",
        "review": "Нужен менеджер",
        "duplicate": "Повтор — деньги уже засчитаны",
        "rejected": "Не платёжный документ",
    }.get(result.verdict, result.verdict)

    parts = [f"{head}: {result.reason}"]
    if doc.is_payment:
        parts.append(
            f"Плательщик: {doc.payer or '—'}"
            + (f" (БИН {doc.payer_bin})" if doc.payer_bin else "")
        )
        parts.append(
            f"Получатель: {doc.payee or '—'}"
            + (f" (БИН {doc.payee_bin})" if doc.payee_bin else "")
        )
        parts.append(f"Сумма: {doc.amount} {doc.currency}, дата {doc.paid_at or '—'}")
        if doc.purpose:
            parts.append(f"Назначение: {doc.purpose}")
        if doc.bank:
            parts.append(f"Банк: {doc.bank}")
    return "\n".join(parts)


def today_iso() -> str:
    return hotel_today().isoformat()
