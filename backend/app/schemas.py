"""Схемы запросов и ответов."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    shortName: str = Field(validation_alias="short_name")
    price: int
    area: str
    capacity: int
    beds: str
    summary: str
    description: str
    features: list[str]
    images: list[str]
    sortOrder: int = Field(validation_alias="sort_order")
    isPublished: bool = Field(validation_alias="is_published")


class RoomIn(BaseModel):
    """Создание номера. Slug задаётся один раз и потом не меняется —
    на него завязаны адреса страниц и ссылки в поисковиках."""

    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,58}$")
    name: str = Field(min_length=2, max_length=160)
    shortName: str = Field(min_length=1, max_length=80)
    price: int = Field(ge=0, le=100_000_000)
    area: str = Field(default="", max_length=40)
    capacity: int = Field(default=2, ge=1, le=10)
    beds: str = Field(default="", max_length=120)
    summary: str = Field(default="", max_length=600)
    description: str = Field(default="", max_length=4000)
    features: list[str] = Field(default_factory=list)


class RoomPatch(BaseModel):
    """Частичное обновление: приходит только то, что реально поменяли."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    shortName: str | None = Field(default=None, min_length=1, max_length=80)
    price: int | None = Field(default=None, ge=0, le=100_000_000)
    area: str | None = Field(default=None, max_length=40)
    capacity: int | None = Field(default=None, ge=1, le=10)
    beds: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=600)
    description: str | None = Field(default=None, max_length=4000)
    features: list[str] | None = None
    images: list[str] | None = None
    sortOrder: int | None = None
    isPublished: bool | None = None


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class LoginOut(BaseModel):
    token: str
    expiresAt: int
    username: str


class LeadIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=40)
    email: str | None = Field(default=None, max_length=160)

    checkIn: str | None = Field(default=None, max_length=20)
    checkOut: str | None = Field(default=None, max_length=20)
    adults: int = Field(default=2, ge=1, le=10)
    room: str | None = Field(default=None, max_length=60)
    comment: str | None = Field(default=None, max_length=1000)

    # honeypot: люди это поле не видят
    company: str | None = None

    @field_validator("phone")
    @classmethod
    def phone_has_enough_digits(cls, v: str) -> str:
        if sum(c.isdigit() for c in v) < 10:
            raise ValueError("Телефон указан некорректно")
        return v


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    name: str
    phone: str
    email: str | None
    check_in: str | None
    check_out: str | None
    adults: int
    room: str | None
    comment: str | None
    status: str


class LeadStatusIn(BaseModel):
    status: str = Field(pattern="^(new|contacted|confirmed|cancelled)$")


class PaymentInitIn(BaseModel):
    """Запрос на создание платежа. Заполняется сайтом при онлайн-оплате."""

    lead_id: int | None = None
    amount: int = Field(gt=0, description="Сумма в тенге")
    description: str = Field(default="Проживание в отеле Airis Residence", max_length=255)
    email: str | None = None
    phone: str | None = None


class PaymentInitOut(BaseModel):
    order_id: str
    payment_url: str
    status: str
