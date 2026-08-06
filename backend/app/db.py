"""Подключение к базе и модели."""

import logging
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func, inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
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

    Свой пул при этом держать не нужно: пулер снаружи уже всё делает,
    а каждая функция живёт секунды.
    """
    if settings.database_url.startswith("sqlite"):
        return {}

    return {
        "poolclass": NullPool,
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
    price: Mapped[int] = mapped_column(Integer)          # тенге за ночь
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


logger = logging.getLogger(__name__)

# Колонки, добавленные после первого запуска. Ключ — таблица.
_LATE_COLUMNS: dict[str, dict[str, str]] = {
    "rooms": {
        "video": "VARCHAR(500) DEFAULT ''",
        "video_poster": "VARCHAR(500) DEFAULT ''",
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
