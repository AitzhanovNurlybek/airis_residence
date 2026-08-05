"""Подключение к базе и модели."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug, future=True)
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


async def init_db() -> None:
    """Создаёт таблицы. Для боевого проекта заменить на alembic-миграции."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with SessionLocal() as session:
        yield session


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
