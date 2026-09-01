"""Подключение к базе и модели."""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    inspect,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import get_settings

settings = get_settings()


def _engine_options() -> dict:
    """
    Настройки подключения зависят от того, где мы работаем.

    Локально это SQLite — файл, ничего настраивать не нужно.

    В облаке это Postgres, к которому serverless-функции подключаются
    через пулер (pgbouncer у Neon и Supabase). У пулера в режиме
    транзакций не работают подготовленные запросы, которые asyncpg
    создаёт по умолчанию, — отсюда ошибки вида «prepared statement
    already exists». Лечится отключением их кэша.

    Пул соединений держим свой, вопреки распространённому совету
    «на serverless он не нужен». Совет верен, когда база рядом. У нас
    она в другом полушарии, и полное рукопожатие (TCP, TLS, авторизация)
    стоит нескольких перелётов через океан — это и было почти две
    секунды на каждой странице. Экземпляр функции живёт минутами и
    обслуживает много запросов подряд, поэтому соединение выгоднее
    переиспользовать.

    Соединений держим мало: их и так ограничивает пулер снаружи.
    pre_ping — дешёвая проверка «живо ли» (один перелёт вместо
    рукопожатия целиком), иначе на подобранном мёртвом соединении
    гость получит ошибку.
    """
    if settings.database_url.startswith("sqlite"):
        return {}

    return {
        "pool_size": 1,
        "max_overflow": 4,
        "pool_timeout": 10,
        # Пулер Supabase закрывает простаивающие соединения сам —
        # обновляем раньше, чем он это сделает.
        "pool_recycle": 240,
        "pool_pre_ping": True,
        "connect_args": {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            # Облачные Postgres требуют TLS
            "ssl": "require" if settings.database_ssl else None,
        },
    }


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    **_engine_options(),
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Room(Base):
    """
    Тип номера. Это то, что редактируется в админке: цена, тексты, фото.

    До появления бэкенда номера жили в `frontend/lib/site.ts`. Тот файл
    остался как аварийный запас: если API недоступен, сайт покажет его.
    Первичное наполнение базы берётся оттуда же (см. seed_rooms.py).
    """

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)

    name: Mapped[str] = mapped_column(String(160))
    short_name: Mapped[str] = mapped_column(String(80))
    price: Mapped[int] = mapped_column(Integer)          # тенге за ночь, одного гостя

    # Система бронирования отеля считает цену от числа гостей, а не от номера:
    # в Comfort + один гость стоит 50 000, а двое — 52 500. Раньше у нас была
    # одна цена на номер, и на двоих сайт недобирал 2 500 за ночь.
    #
    # Ноль означает «столько же, сколько за одного» — так у большинства
    # категорий, и заполнять поле ради равенства не нужно.
    price_double: Mapped[int] = mapped_column(Integer, default=0)

    # Доплата за дополнительное место. Ноль — доп. места нет.
    # Ребёнок до 6 лет занимает его бесплатно, это записано в правилах отеля.
    extra_bed_price: Mapped[int] = mapped_column(Integer, default=0)
    area: Mapped[str] = mapped_column(String(40))
    capacity: Mapped[int] = mapped_column(Integer, default=2)
    beds: Mapped[str] = mapped_column(String(120), default="")

    summary: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")

    features: Mapped[list] = mapped_column(JSON, default=list)
    images: Mapped[list] = mapped_column(JSON, default=list)
    # Ссылка на видеообзор номера. Файл лежит в том же хранилище, что и фото,
    # но грузится напрямую из браузера — см. rooms_api, выдача временной ссылки.
    video: Mapped[str] = mapped_column(String(500), default="")
    # Кадр из этого же ролика. Обложка из фотографий не годится: снимают
    # вертикально, а фото горизонтальные — при клике картинка прыгала бы.
    video_poster: Mapped[str] = mapped_column(String(500), default="")

    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SiteVideo(Base):
    """
    Видеообзор, не привязанный к номеру: кухня, лобби, общие зоны.

    Отдельная таблица, а не поле у номера, потому что таких роликов
    со временем становится больше одного, и каждому нужен свой
    заголовок и своё место в списке.
    """

    __tablename__ = "site_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)

    title: Mapped[str] = mapped_column(String(160), default="")
    summary: Mapped[str] = mapped_column(String(400), default="")

    video: Mapped[str] = mapped_column(String(500), default="")
    video_poster: Mapped[str] = mapped_column(String(500), default="")

    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Lead(Base):
    """Заявка на бронирование, оставленная через форму на сайте."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)

    check_in: Mapped[str | None] = mapped_column(String(20), nullable=True)
    check_out: Mapped[str | None] = mapped_column(String(20), nullable=True)
    adults: Mapped[int] = mapped_column(Integer, default=0)
    room: Mapped[str | None] = mapped_column(String(60), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # new | contacted | confirmed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    source: Mapped[str] = mapped_column(String(40), default="site")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Payment(Base):
    """
    Платёж. Заполняется, когда подключат эквайринг банка.
    Пока таблица есть, но запись в неё создаётся только через
    /api/payments/* — эндпоинты вернут 501, если банк не настроен.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    lead_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    amount: Mapped[int] = mapped_column(Integer)          # в тиынах, чтобы не терять копейки
    currency: Mapped[str] = mapped_column(String(3), default="KZT")

    # created | pending | paid | failed | refunded
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_callback: Mapped[str | None] = mapped_column(Text, nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ────────────────────── Корпоративный кабинет (B2B) ──────────────────────
#
# Отдельный контур: у компаний своя авторизация, свои цены и свои брони.
# С публичным сайтом он пересекается только справочником номеров: номер тот
# же самый, отличается цена и то, кто и как его бронирует.


class Company(Base):
    """
    Компания-клиент, с которой подписан договор.

    Реквизиты (БИН, номер и дата договора, условия оплаты) лежат полями, а не
    текстом: их видит сотрудник компании в кабинете, и они же идут в счёт.
    Менеджер Airis тоже привязан к компании — у каждого корпоративного
    клиента свой человек со стороны отеля.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Короткий код: адреса в админке и номера счетов. Меняться не должен.
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    bin: Mapped[str] = mapped_column(String(12), default="")

    contract_number: Mapped[str] = mapped_column(String(60), default="")
    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Свободный текст: «постоплата, 30 дн. (после услуг)». Вариантов у разных
    # компаний слишком много, чтобы загонять их в справочник.
    payment_terms: Mapped[str] = mapped_column(String(200), default="")

    manager_name: Mapped[str] = mapped_column(String(160), default="")
    manager_email: Mapped[str] = mapped_column(String(160), default="")
    manager_phone: Mapped[str] = mapped_column(String(40), default="")

    # Скидка на весь прайс — обычный случай в договоре: «минус 12 % от стойки».
    # Точечная цена на конкретный номер задаётся в CompanyRate и важнее.
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)

    # Сколько снимать за отказ от завтрака — на гостя за ночь.
    #
    # Завтрак у отеля входит в цену любого номера, поэтому «без завтрака» —
    # это вычет, а не доплата. Величина живёт у компании, а не у отеля:
    # это условие договора, и у разных компаний оно разное.
    #
    # Ноль — обычный случай: цена та же, но выбор всё равно записывается.
    # Кухне важно знать, сколько человек придёт утром, даже когда деньги
    # от этого не меняются.
    breakfast_price: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CompanyUser(Base):
    """
    Сотрудник компании, входящий в кабинет.

    Пароль хранится хешем (corp_auth.hash_password) — в отличие от админки
    отеля, где одна учётка на весь отель и логин лежит в окружении. Здесь
    пользователей много, они приходят и уходят, поэтому нужна таблица.

    Роли всего две. `admin` заводит и отключает коллег и видит расходы всей
    компании; `employee` бронирует и видит только свои брони. Больше
    градаций заказчик не просил, а лишние роли всегда дороже, чем кажутся.
    """

    __tablename__ = "company_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )

    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    full_name: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")

    role: Mapped[str] = mapped_column(String(20), default="employee", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CompanyRate(Base):
    """
    Корпоративная цена на конкретный тип номера.

    Привязка к номеру идёт по slug, а не по id. Slug — внешний код номера: он
    же в адресах страниц и в документах для интеграторов, и именно его сверяют
    с системой бронирования. Числовой id живёт только внутри базы.
    """

    __tablename__ = "company_rates"
    __table_args__ = (UniqueConstraint("company_id", "room_slug", name="uq_company_room"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    room_slug: Mapped[str] = mapped_column(String(60), index=True)
    price: Mapped[int] = mapped_column(Integer)  # тенге за ночь
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CorpBooking(Base):
    """
    Бронирование, оформленное компанией.

    Пока система бронирования отеля не отдаёт API, это заявка: сотрудник
    оформляет её сам по корпоративным ценам, менеджер подтверждает и
    выставляет счёт. Когда API появится, добавится поле с внешним номером
    брони, а жизненный цикл останется прежним — поэтому статусы описывают
    состояние сделки, а не то, кто её обрабатывает.

    Статусы: new (отправлена) → confirmed (менеджер подтвердил) →
    invoiced (счёт выставлен) → paid; cancelled — на любом шаге до paid.
    """

    __tablename__ = "corp_bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Человеческий номер для писем и счетов: его называют менеджеру.
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    # Кто оформил. Сотрудника могут отключить, а бронь останется —
    # поэтому SET NULL, а не CASCADE.
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("company_users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Портал заказчика спроектирован под несколько отелей (/hotels/airis).
    # У нас отель пока один, но поле есть с самого начала: добавить его
    # позже — значит переписывать все брони задним числом.
    hotel_slug: Mapped[str] = mapped_column(String(60), default="airis", index=True)

    check_in: Mapped[date] = mapped_column(Date, index=True)
    check_out: Mapped[date] = mapped_column(Date)
    nights: Mapped[int] = mapped_column(Integer, default=1)

    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)

    # Кто именно едет. Часто это не тот, кто оформляет бронь: секретарь
    # бронирует для руководителя.
    guest_name: Mapped[str] = mapped_column(String(200), default="")
    guest_phone: Mapped[str] = mapped_column(String(40), default="")
    comment: Mapped[str] = mapped_column(Text, default="")

    # breakfast — завтрак включён (обычный случай), none — гость от него
    # отказался. Хранится у брони, а не считается из суммы: через полгода по
    # сумме уже не понять, был вычет или просто другая цена.
    meal_plan: Mapped[str] = mapped_column(String(20), default="breakfast")

    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)  # тенге

    invoice_number: Mapped[str] = mapped_column(String(60), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_reason: Mapped[str] = mapped_column(String(300), default="")


class CorpBookingItem(Base):
    """
    Строка брони: столько-то номеров такой-то категории по такой-то цене.

    Название номера и цена копируются сюда снимком, а не берутся из Room при
    показе. Причина проверена на своей шкуре: номер «Luxe» переименовали в
    «Comfort Plus», и все прошлые документы стали бы противоречить сами себе.
    Договорённость на момент брони не должна меняться задним числом.
    """

    __tablename__ = "corp_booking_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("corp_bookings.id", ondelete="CASCADE"), index=True
    )

    room_slug: Mapped[str] = mapped_column(String(60), index=True)
    room_name: Mapped[str] = mapped_column(String(160), default="")
    rooms_count: Mapped[int] = mapped_column(Integer, default=1)
    price_per_night: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[int] = mapped_column(Integer, default=0)


logger = logging.getLogger(__name__)

class LocalStock(Base):
    """
    Сколько номеров каждого типа есть у отеля — в локальной шахматке.

    Это не про сайт и не про корпоративный кабинет. Это учебная копия того,
    чем заведует Exely: сколько физических номеров существует. У нас такой
    таблицы раньше не было вовсе — сайт знает категории и цены, но не знает,
    сколько комнат каждой категории стоит в здании.
    """

    __tablename__ = "local_stock"

    room_slug: Mapped[str] = mapped_column(String(60), primary_key=True)
    rooms_total: Mapped[int] = mapped_column(Integer, default=0)


class LocalBooking(Base):
    """
    Бронь в локальной шахматке.

    Намеренно отдельная таблица от CorpBooking. Это разные сущности: здесь —
    занятость номера, всё равно кем и через какой канал; там — заявка компании
    с договорной ценой и счётом. Свести их в одну таблицу значит смешать
    «комната занята» и «компания должна денег», а это разные жизненные циклы.

    Когда подключится настоящий Exely, эта таблица уйдёт целиком: её место
    займут ответы чужого API. Поэтому здесь нет ничего, чего не может дать
    внешняя система, — иначе при переходе всплывут потерянные поля.
    """

    __tablename__ = "local_bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Номер, который называют гостю. Из него же гость его потом находит.
    ref: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    room_slug: Mapped[str] = mapped_column(String(60), index=True)
    rooms_count: Mapped[int] = mapped_column(Integer, default=1)

    check_in: Mapped[date] = mapped_column(Date, index=True)
    check_out: Mapped[date] = mapped_column(Date, index=True)

    guest_name: Mapped[str] = mapped_column(String(200), default="")
    guest_phone: Mapped[str] = mapped_column(String(40), default="", index=True)

    #: booked — номер занят; cancelled — освобождён.
    status: Mapped[str] = mapped_column(String(20), default="booked", index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)

    #: Откуда бронь: concierge (ИИ в переписке), seed (фоновая занятость),
    #: manual (завели руками при отладке).
    origin: Mapped[str] = mapped_column(String(20), default="manual", index=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LocalPayment(Base):
    """
    Принятая платёжка — чтобы не принять её второй раз.

    В переписке гость пересылает один и тот же чек по три раза: «вы получили?»,
    «на всякий случай ещё», «вот скрин». Без этой таблицы каждая пересылка
    добавляла бы оплату заново, и бронь на сто тысяч оказывалась бы оплаченной
    на триста.

    Один и тот же платёж узнаём двумя способами. Совпал хеш файла — прислали
    тот же самый документ. Совпали номер документа, сумма и бронь — тот же
    платёж, но переснятый или пересохранённый: байты другие, деньги те же.
    """

    __tablename__ = "local_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(20), index=True)

    #: SHA-256 присланного файла.
    doc_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    #: Номер документа из самой платёжки.
    doc_number: Mapped[str] = mapped_column(String(60), default="", index=True)

    amount: Mapped[int] = mapped_column(Integer, default=0)
    payer: Mapped[str] = mapped_column(String(200), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ExelyEvent(Base):
    """
    Уведомление от Exely: бронь создана или отменена.

    Зачем хранить, а не обработать на лету. Гость оформляет бронь в форме
    Exely — сами мы её не заводим и узнать о ней иначе не можем. Вебхук
    приходит в веб-приложение, а с гостем переписывается отдельный процесс
    бота: передать событие из одного в другой можно только через базу.

    Тело сохраняется целиком строкой JSON. Разбор полей у Exely мы пишем по
    документации, живых ответов ещё не видели, и первое же расхождение
    разбирать будет не по чему, если сохранить только то, что поняли.

    Повторы Exely присылает штатно: если мы ответили не сразу, уведомление
    придёт снова. Отсюда `event_key` с уникальным индексом.
    """

    __tablename__ = "exely_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: Чем отличаем повтор от нового события: тип + номер брони.
    event_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    #: Что произошло, словом Exely: created, cancelled и т.д.
    kind: Mapped[str] = mapped_column(String(60), default="", index=True)
    booking_number: Mapped[str] = mapped_column(String(60), default="", index=True)
    guest_phone: Mapped[str] = mapped_column(String(40), default="", index=True)

    #: Сырое тело уведомления, как прислали.
    payload: Mapped[str] = mapped_column(Text, default="")

    #: Отработал ли по нему бот (написал гостю, обновил разговор).
    handled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ExelyBooking(Base):
    """
    Копия брони из Exely — чтобы искать её по имени гостя.

    Зачем копия. Гость, забывший номер брони, называет своё имя. А имя в
    Exely лежит только в детальном запросе по каждой броне отдельно: в
    списке есть лишь номер, статус и дата изменения. Замерено: собрать имена
    всех броней отеля — двенадцать минут. В переписке столько не ждут.

    Поэтому брони переносятся сюда заранее, порциями, по расписанию. Поиск
    по имени идёт уже здесь и занимает миллисекунды.

    Хранится только то, что нужно для ответа гостю о его же броне. Ни карт,
    ни паспортов, ни адресов — этого и в API нет.
    """

    __tablename__ = "exely_bookings"

    number: Mapped[str] = mapped_column(String(60), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), default="", index=True)

    #: Имя целиком, как в Exely, и оно же в нижнем регистре — по второму
    #: идёт поиск. Отдельная колонка, а не приведение при запросе: иначе
    #: индекс не работает и поиск идёт перебором всей таблицы.
    guest_name: Mapped[str] = mapped_column(String(200), default="")
    guest_search: Mapped[str] = mapped_column(String(200), default="", index=True)

    check_in: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    check_out: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    room_name: Mapped[str] = mapped_column(String(120), default="")

    #: Когда бронь последний раз менялась в Exely. По нему решаем, надо ли
    #: перечитывать деталь: неизменившиеся не трогаем.
    modified_at: Mapped[str] = mapped_column(String(40), default="")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DialogMessage(Base):
    """
    Одна реплика переписки с гостем.

    Нужна, потому что разговор в мессенджере не заканчивается: гость спросил
    цену, ушёл на полдня, вернулся с «а на выходные?». Без истории он каждый
    раз начинает с нуля, и консьерж переспрашивает то, что уже знает.

    Содержимое хранится строкой JSON, а не текстом. Реплика — не всегда фраза:
    когда консьерж лезет в систему бронирования, в истории оказываются блоки
    вызова инструмента и его ответа. Потерять их нельзя — без них модель не
    поймёт, откуда взялись числа в собственном прошлом ответе.
    """

    __tablename__ = "dialog_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: whatsapp | instagram | admin — откуда пришло.
    channel: Mapped[str] = mapped_column(String(20), index=True)
    #: Идентификатор собеседника внутри канала. У WhatsApp это chatId.
    chat_id: Mapped[str] = mapped_column(String(80), index=True)

    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ChannelReceipt(Base):
    """
    Отметка «это сообщение мы уже обработали».

    Green API подтверждение приёма может не пройти, и тогда то же сообщение
    придёт снова. Без этой таблицы гость получил бы два одинаковых ответа, а
    в худшем случае — две одинаковые брони.
    """

    __tablename__ = "channel_receipts"

    #: Идентификатор сообщения в канале. У Green API это idMessage.
    message_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class DialogFollowup(Base):
    """
    Отметка «по этому разговору мы уже написали вдогонку».

    Гость, спросивший про номера и пропавший, получает напоминание — но
    строго ограниченное число раз. Считать отправленное по самой переписке
    нельзя: напоминание лежит в ней такой же строкой, как обычный ответ, и
    отличить одно от другого потом нечем.

    Отдельная таблица заодно даёт бесплатный сброс. Отметки учитываются
    только те, что легли ПОСЛЕ последней реплики гостя: написал — значит
    разговор живой, и счёт начинается заново. Отдельного сброса писать не
    пришлось, а значит, и забыть его негде.
    """

    __tablename__ = "dialog_followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    chat_id: Mapped[str] = mapped_column(String(80), index=True)
    #: Какое по счёту: 1 — вернуть к разговору, 2 — попрощаться. Третьего нет.
    step: Mapped[int] = mapped_column(Integer, default=1)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SeenPayment(Base):
    """Платёж, о котором банк сообщил уведомлением.

    Единственный способ связать бронь с платежом. Поддержка FreedomPay
    ответила прямо: искать платежи по описанию через API нельзя, «такого
    API нет», фильтры есть только в кабинете. Зато «по каждому платежу мы
    отправляем коллбэки», и в них приходит `pg_description` — а туда Exely
    записывает номер брони целиком.

    Отсюда замысел: ловить уведомления, запоминать номер платежа рядом с
    описанием, и при отмене находить нужный платёж у себя, никуда не
    обращаясь. Поиск, которого нет у банка, получается из данных, которые
    банк присылает сам.
    """

    __tablename__ = "seen_payments"

    #: Номер платежа в системе банка. Он же ключ: одно уведомление на платёж
    #: может прийти несколько раз, и заводить дубли незачем.
    payment_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    #: Номер заказа на стороне того, кто создал платёж (у Exely вида PG1798).
    order_id: Mapped[str] = mapped_column(String(60), default="", index=True)
    #: Описание заказа. Здесь и лежит номер брони — по нему ищем.
    description: Mapped[str] = mapped_column(String(400), default="", index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="KZT")
    #: paid | failed | pending — как разобрал parse_callback.
    status: Mapped[str] = mapped_column(String(16), default="", index=True)
    card: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class BookingCheck(Base):
    """Отметка «эту бронь мы уже проверяли на оплату».

    Через сутки после создания бронь проверяется: внесена ли предоплата.
    Неоплаченная — повод отелю позвонить гостю, пока номер не простоял
    впустую.

    Отметка нужна, чтобы не спрашивать дважды. Без неё каждый суточный
    запуск слал бы отелю один и тот же список, и его перестали бы читать
    ровно так же, как перестают читать любое повторяющееся уведомление.
    """

    __tablename__ = "booking_checks"

    number: Mapped[str] = mapped_column(String(60), primary_key=True)
    #: Что выяснилось: paid | unpaid | gone (отменена или не прочиталась) |
    #: elsewhere (бронь с площадки, а не с сайта отеля).
    verdict: Mapped[str] = mapped_column(String(16), default="")
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class GuestName(Base):
    """Имя, которое гость назвал в переписке перед бронированием.

    Единственный мостик между чатом и бронью. Exely не отдаёт ни телефона,
    ни почты — только имя и фамилию, — а WhatsApp знает телефон, но не знает
    брони. Совпадение имён связывает одно с другим.

    Мостик не идеальный: однофамильцы существуют. Поэтому по нему можно
    только НАПОМНИТЬ гостю о его же броне, и только когда совпадение
    единственное. Показывать по имени чужие данные нельзя.
    """

    __tablename__ = "guest_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    chat_id: Mapped[str] = mapped_column(String(80), index=True)
    #: Как гость себя назвал, в нижнем регистре — для сравнения.
    name: Mapped[str] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


# Колонки, добавленные после первого запуска. Ключ — таблица.
_LATE_COLUMNS: dict[str, dict[str, str]] = {
    "rooms": {
        "video": "VARCHAR(500) DEFAULT ''",
        "video_poster": "VARCHAR(500) DEFAULT ''",
        "price_double": "INTEGER DEFAULT 0",
        "extra_bed_price": "INTEGER DEFAULT 0",
    },
    "companies": {
        "breakfast_price": "INTEGER DEFAULT 0",
    },
    "corp_bookings": {
        "meal_plan": "VARCHAR(20) DEFAULT 'breakfast'",
    },
}


def _add_late_columns(conn) -> None:
    """
    Догоняет схему на базе, которая уже существует.

    create_all создаёт только недостающие таблицы и не трогает колонки
    существующих. Значит новое поле на работающем сайте пришлось бы
    добавлять руками. Полноценный alembic ради одной-двух колонок —
    перебор, поэтому добавляем их здесь: проверка дешёвая, а пропущенная
    миграция на проде стоит дорого.
    """
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    for table, columns in _LATE_COLUMNS.items():
        if table not in tables:
            continue  # create_all только что создал её сразу с колонками
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name in existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            logger.info("База: добавлена колонка %s.%s", table, name)


async def init_db() -> None:
    """Создаёт таблицы. Для боевого проекта заменить на alembic-миграции."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_late_columns)


async def get_session():
    async with SessionLocal() as session:
        yield session


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
