"""
Проверка разбора платёжных документов.

Квитанции рисуются здесь же — иначе тест зависел бы от чужих файлов, которые
никто не положит в репозиторий. Форма нарочно разная: чистое поручение,
кривоватый чек, документ с отклонённым платежом, вообще не платёжка.

Главное, за чем следит этот тест, — не «модель прочитала правильно», а «сервер
не отметил оплату там, где не должен». Ошибка в чтении стоит вопроса
менеджеру; ошибка в отметке — заселённого гостя, который не платил.

Запуск (нужен ключ Anthropic в .env):
    python e2e_payment.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.booking_system import get_booking_system  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.knowledge import load_facts, reset_cache  # noqa: E402
from app.payment_docs import (  # noqa: E402
    check_recipient,
    describe,
    match_and_apply,
    read_document,
)

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000").rstrip("/")

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_pay_tmp")

passed = 0
failed: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
        print(f"    ✓ {name}")
    else:
        failed.append(name)
        print(f"    ✗ {name}" + (f" — {detail}" if detail else ""))


def _font(size: int):
    for candidate in ("arial.ttf", "segoeui.ttf", "tahoma.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_pdf(name: str, lines: list[tuple[str, int]]) -> str:
    """Нарисовать документ и сохранить в PDF."""
    os.makedirs(TMP, exist_ok=True)
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    y = 90
    for text, size in lines:
        draw.text((90, y), text, fill="black", font=_font(size))
        y += int(size * 1.9)
    path = os.path.join(TMP, name)
    image.save(path, "PDF", resolution=150)
    return path


async def main() -> int:
    settings = Settings(booking_system="local", site_url=BASE)
    if not settings.anthropic_api_key:
        print("Ключ Anthropic не задан в .env — прогон невозможен")
        return 1

    await init_db()
    booking = get_booking_system(settings)

    # Реквизиты отеля берём оттуда же, откуда их берёт консьерж, — иначе
    # проверка получателя сверялась бы с копией, которая однажды отстанет.
    reset_cache()
    try:
        facts = await load_facts(settings)
    except Exception as error:  # noqa: BLE001
        print(f"Не удалось получить справку об отеле с {settings.site_url}: {error}")
        print("Поднимите фронтенд на 3000 — без реквизитов проверка получателя невозможна.")
        return 1
    OUR_BIN = facts["hotel"]["legal"]["bin"]
    OUR_IIK = facts["hotel"]["legal"]["iik"]
    print(f"Реквизиты отеля: БИН {OUR_BIN}")

    check_in = date.today() + timedelta(days=30)
    check_out = check_in + timedelta(days=2)
    made = await booking.create_booking(
        room_slug="comfort",
        rooms_count=1,
        check_in=check_in,
        check_out=check_out,
        guest_name="Асель Нурланова",
        guest_phone="+7 707 123 45 67",
        amount=100000,
        origin="manual",
    )
    ref = made.external_id
    print(f"Бронь для проверки: {ref}, начислено {made.total_amount} ₸\n")

    # ── 1. Обычное платёжное поручение ──
    print("── Платёжное поручение с номером брони ──")
    path = make_pdf(
        "poruchenie.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 417", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("", 20),
            ("Плательщик: ТОО «Астана Строй Инвест»", 34),
            ("БИН: 180340012345", 34),
            ("Банк: АО «Kaspi Bank»", 34),
            ("", 20),
            ("Получатель: ТОО «INCOME HOUSE»", 34),
            (f"БИН получателя: {OUR_BIN}", 32),
            (f"ИИК: {OUR_IIK}", 28),
            ("", 20),
            ("Сумма: 100 000,00 тенге", 42),
            ("", 20),
            (f"Назначение платежа: оплата за проживание,", 32),
            (f"бронь {ref}, гость Нурланова А.", 32),
            ("", 20),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "poruchenie.pdf")
    print(f"   прочитано: {doc.payer} · {doc.amount} {doc.currency} · ссылка «{doc.reference}»")
    check("узнал платёжку", doc.is_payment)
    check("сумма прочитана", doc.amount == 100000, str(doc.amount))
    check("плательщик прочитан", "Астана" in doc.payer, doc.payer)
    check("БИН прочитан", "180340012345" in doc.payer_bin, doc.payer_bin)

    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("оплата отмечена", result.verdict == "applied", result.reason)
    check("нашлась нужная бронь", result.booking_ref == ref, result.booking_ref)

    invoices = await booking.invoices(external_id=ref)
    check("в счёте видно оплату", bool(invoices) and invoices[0].paid_amount == 100000,
          str(invoices[0].paid_amount) if invoices else "нет счёта")
    check("счёт закрыт", bool(invoices) and invoices[0].status == "paid")

    # ── 2. Без номера брони ──
    print("\n── Квитанция без номера брони ──")
    path = make_pdf(
        "bez-nomera.pdf",
        [
            ("Kaspi Bank — Чек об оплате", 44),
            (f"Дата: {date.today().strftime('%d.%m.%Y')} 14:32", 32),
            ("", 20),
            ("Отправитель: Асель Н.", 34),
            ("Получатель: INCOME HOUSE TOO", 34),
            ("", 20),
            ("Сумма: 45 000 ₸", 42),
            ("Комментарий: за отель", 32),
            ("", 20),
            ("Успешно", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "bez-nomera.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("без номера брони отдал менеджеру", result.verdict == "review", result.verdict)
    check("причина названа понятно", "номер" in result.reason.lower(), result.reason)

    # ── 3. Отклонённый платёж ──
    print("\n── Отклонённый платёж ──")
    path = make_pdf(
        "otkloneno.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 512", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("", 20),
            ("Плательщик: ИП Ким В.", 34),
            (f"Получатель: ТОО «INCOME HOUSE», БИН {OUR_BIN}", 30),
            ("Сумма: 100 000,00 тенге", 42),
            (f"Назначение: бронь {ref}", 32),
            ("", 20),
            ("Статус: ОТКЛОНЕНО БАНКОМ", 40),
            ("Причина: недостаточно средств", 30),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "otkloneno.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("отклонённый платёж не засчитан", result.verdict == "review", result.verdict)

    # ── 4. Сумма больше начисленной ──
    print("\n── Сумма больше, чем по брони ──")
    second = await booking.create_booking(
        room_slug="standart",
        rooms_count=1,
        check_in=check_in,
        check_out=check_out,
        guest_name="Ерлан Тулеу",
        guest_phone="+7 700 555 44 33",
        amount=90000,
        origin="manual",
    )
    path = make_pdf(
        "pereplata.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 900", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("Плательщик: ТОО «Меркурий»", 34),
            (f"Получатель: ТОО «INCOME HOUSE», БИН {OUR_BIN}", 30),
            ("Сумма: 250 000,00 тенге", 42),
            (f"Назначение: оплата брони {second.external_id}", 32),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "pereplata.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("переплату не проглотил молча", result.verdict == "review", result.verdict)
    after = await booking.invoices(external_id=second.external_id)
    check("лишние деньги не записаны", not after or after[0].paid_amount == 0,
          str(after[0].paid_amount) if after else "нет счёта")

    # ── 5. Несуществующая бронь ──
    print("\n── Ссылка на несуществующую бронь ──")
    path = make_pdf(
        "chuzhaya.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 001", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("Плательщик: Иванов И.", 34),
            (f"Получатель: ТОО «INCOME HOUSE», БИН {OUR_BIN}", 30),
            ("Сумма: 50 000,00 тенге", 42),
            ("Назначение: оплата брони L-9999", 32),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "chuzhaya.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("несуществующую бронь не выдумал", result.verdict == "review", result.verdict)

    # ── 6. Вообще не платёжка ──
    print("\n── Не платёжный документ ──")
    path = make_pdf(
        "menu.pdf",
        [
            ("МЕНЮ ЗАВТРАКА", 52),
            ("Шведский стол 07:00 — 10:30", 36),
            ("", 20),
            ("Каша овсяная, омлет, блины", 32),
            ("Нарезки, фрукты, выпечка", 32),
            ("Чай, кофе, соки", 32),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "menu.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("меню не приняло за платёжку", result.verdict == "rejected", result.verdict)

    # ── 7. Повторная присылка того же документа ──
    print("\n── Ту же платёжку прислали дважды ──")
    with open(os.path.join(TMP, "poruchenie.pdf"), "rb") as f:
        doc = await read_document(settings, f.read(), "poruchenie.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    invoices = await booking.invoices(external_id=ref)
    check("повтор распознан", result.verdict == "duplicate", result.verdict)
    check("вторая отметка не удвоила оплату",
          bool(invoices) and invoices[0].paid_amount == 100000,
          str(invoices[0].paid_amount) if invoices else "нет счёта")

    # Переснятый чек: файл другой, номер документа и сумма те же
    print("\n── Тот же платёж, но пересохранённый файл ──")
    path = make_pdf(
        "poruchenie-copy.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 417", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("Плательщик: ТОО «Астана Строй Инвест»", 34),
            (f"Получатель: ТОО «INCOME HOUSE», БИН {OUR_BIN}", 30),
            ("Сумма: 100 000,00 тенге", 42),
            (f"Назначение платежа: оплата за проживание, бронь {ref}", 30),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "poruchenie-copy.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("переснятый чек тоже не удвоил оплату",
          result.verdict in ("duplicate", "review"), result.verdict)
    invoices = await booking.invoices(external_id=ref)
    check("сумма оплаты осталась прежней",
          bool(invoices) and invoices[0].paid_amount == 100000,
          str(invoices[0].paid_amount) if invoices else "нет счёта")

    # ── 8. Платёж ушёл чужой компании ──
    print("\n── Деньги ушли не отелю ──")
    path = make_pdf(
        "chuzhoy-poluchatel.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 777", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("Плательщик: ТОО «Астана Строй Инвест»", 34),
            ("Получатель: ТОО «ОТЕЛЬ СОСЕДНИЙ»", 34),
            ("БИН получателя: 111111111111", 32),
            ("Сумма: 90 000,00 тенге", 42),
            (f"Назначение: оплата брони {second.external_id}", 32),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "chuzhoy-poluchatel.pdf")
    status_, why = check_recipient(doc, facts)
    print(f"   получатель: {status_} — {why}")
    check("чужой получатель распознан", status_ == "mismatch", status_)
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("платёж чужой компании отклонён", result.verdict == "rejected", result.verdict)
    inv = await booking.invoices(external_id=second.external_id)
    check("деньги по чужой платёжке не засчитаны",
          not inv or inv[0].paid_amount == 0, str(inv[0].paid_amount) if inv else "нет счёта")

    # ── 9. Сумма прописью не сходится с цифрами ──
    print("\n── Сумма прописью против цифр ──")
    path = make_pdf(
        "propisyu.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 321", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("Плательщик: ТОО «Астана Строй Инвест»", 34),
            (f"Получатель: ТОО «INCOME HOUSE», БИН {OUR_BIN}", 30),
            ("Сумма: 90 000,00 тенге", 42),
            ("Сумма прописью: сорок пять тысяч тенге 00 тиын", 30),
            (f"Назначение: оплата брони {second.external_id}", 32),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "propisyu.pdf")
    print(f"   цифрами {doc.amount}, прописью «{doc.amount_in_words}»")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("расхождение прописи и цифр поймано", result.verdict == "review", result.verdict)
    inv = await booking.invoices(external_id=second.external_id)
    check("по спорной сумме деньги не засчитаны",
          not inv or inv[0].paid_amount == 0, str(inv[0].paid_amount) if inv else "нет счёта")

    # ── 10. Дата платежа в будущем ──
    print("\n── Дата платежа в будущем ──")
    future = (date.today() + timedelta(days=40)).strftime("%d.%m.%Y")
    path = make_pdf(
        "budushee.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 555", 46),
            (f"Дата: {future}", 34),
            ("Плательщик: ТОО «Астана Строй Инвест»", 34),
            (f"Получатель: ТОО «INCOME HOUSE», БИН {OUR_BIN}", 30),
            ("Сумма: 90 000,00 тенге", 42),
            (f"Назначение: оплата брони {second.external_id}", 32),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "budushee.pdf")
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("дата из будущего поймана", result.verdict == "review", result.verdict)

    # ── 11. Настоящий чек проходит все три проверки ──
    print("\n── Правильный чек на вторую бронь ──")
    path = make_pdf(
        "chistyy.pdf",
        [
            ("ПЛАТЁЖНОЕ ПОРУЧЕНИЕ № 640", 46),
            (f"Дата: {date.today().strftime('%d.%m.%Y')}", 34),
            ("Плательщик: ТОО «Меркурий»", 34),
            ("БИН: 190240055555", 32),
            (f"Получатель: ТОО «INCOME HOUSE», БИН {OUR_BIN}", 30),
            (f"ИИК: {OUR_IIK}", 28),
            ("Сумма: 90 000,00 тенге", 42),
            ("Сумма прописью: девяносто тысяч тенге 00 тиын", 30),
            (f"Назначение: оплата за проживание, бронь {second.external_id}", 30),
            ("Статус: ИСПОЛНЕНО", 34),
        ],
    )
    with open(path, "rb") as f:
        doc = await read_document(settings, f.read(), "chistyy.pdf")
    status_, why = check_recipient(doc, facts)
    print(f"   получатель: {status_} — {why}")
    check("свой получатель распознан", status_ == "ok", why)
    check("правки не заявлено", not doc.looks_edited, "; ".join(doc.red_flags))
    if doc.red_flags:
        print("   замечания модели (не блокируют): " + "; ".join(doc.red_flags)[:200])
    result = await match_and_apply(booking, doc, facts=facts)
    print(f"   вердикт: {result.verdict} — {result.reason}")
    check("чистый чек засчитан", result.verdict == "applied", result.reason)
    inv = await booking.invoices(external_id=second.external_id)
    check("оплата видна в счёте", bool(inv) and inv[0].paid_amount == 90000,
          str(inv[0].paid_amount) if inv else "нет счёта")

    print("\n── Шахматка ──")
    for row in await booking.snapshot():
        print(f"   {row['ref']} {row['guest'] or '—':20} {row['status']:10} "
              f"начислено {row['amount']:>8} · оплачено {row['paid']:>8}")

    total = passed + len(failed)
    print(f"\n── Итог ──\n   {passed} из {total}")
    if failed:
        print("   не прошло: " + "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
