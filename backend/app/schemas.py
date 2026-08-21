"""Схемы запросов и ответов."""

from datetime import date, datetime

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
    video: str = ""
    videoPoster: str = Field(default="", validation_alias="video_poster")
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


class SiteVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    summary: str
    video: str
    videoPoster: str = Field(default="", validation_alias="video_poster")
    sortOrder: int = Field(validation_alias="sort_order")
    isPublished: bool = Field(validation_alias="is_published")


class SiteVideoIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,58}$")
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(default="", max_length=400)


class SiteVideoPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    summary: str | None = Field(default=None, max_length=400)
    sortOrder: int | None = None
    isPublished: bool | None = None


class VideoSignIn(BaseModel):
    """Запрос ссылки на прямую загрузку видео в хранилище."""

    filename: str = Field(min_length=1, max_length=200)
    contentType: str = Field(pattern=r"^video/(mp4|webm|quicktime)$")
    sizeBytes: int = Field(gt=0)


class VideoSignOut(BaseModel):
    uploadUrl: str
    key: str
    # Что положить в заголовок запроса: подпись считалась именно под него,
    # с другим значением хранилище загрузку отклонит.
    contentType: str
    maxBytes: int

    # Кадр-заставка. Браузер вырезает его из выбранного файла сам и грузит
    # туда же — иначе на месте плеера пришлось бы показывать фотографию
    # номера, а она горизонтальная и с вертикальным роликом не совпадает.
    posterUploadUrl: str
    posterKey: str
    posterContentType: str = "image/jpeg"


class VideoConfirmIn(BaseModel):
    """Подтверждение после успешной загрузки: файл проверяем сами."""

    key: str = Field(min_length=1, max_length=300)
    posterKey: str | None = Field(default=None, max_length=300)


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


# ────────────────────── Корпоративный кабинет (B2B) ──────────────────────


class CorpLoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=200)


class CorpLoginOut(BaseModel):
    token: str
    expires_at: int
    role: str
    company_name: str


class CorpPasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    # Восемь символов — нижняя граница, ниже которой пароль перестаёт быть
    # паролем. Требовать спецсимволы не стали: люди в ответ пишут Qwerty1!
    # и записывают на бумажке, а длина работает лучше.
    new_password: str = Field(min_length=8, max_length=200)


class CompanyOut(BaseModel):
    """Карточка компании — то, что сотрудник видит в шапке кабинета."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    bin: str
    contractNumber: str = Field(default="", validation_alias="contract_number")
    contractDate: date | None = Field(default=None, validation_alias="contract_date")
    paymentTerms: str = Field(default="", validation_alias="payment_terms")
    managerName: str = Field(default="", validation_alias="manager_name")
    managerEmail: str = Field(default="", validation_alias="manager_email")
    managerPhone: str = Field(default="", validation_alias="manager_phone")
    discountPercent: int = Field(default=0, validation_alias="discount_percent")


class CompanyUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    fullName: str = Field(default="", validation_alias="full_name")
    phone: str = ""
    role: str
    isActive: bool = Field(default=True, validation_alias="is_active")
    lastLoginAt: datetime | None = Field(default=None, validation_alias="last_login_at")
    # Заведён ли пароль. Само значение наружу не отдаём никогда —
    # только признак, чтобы в списке сотрудников было видно, кто ещё не вошёл.
    hasPassword: bool = False


class CorpMeOut(BaseModel):
    """Всё, что нужно кабинету на первом экране, одним запросом."""

    user: CompanyUserOut
    company: CompanyOut
    activeBookings: int = 0
    totalAmount: int = 0
    paidAmount: int = 0


class CorpRoomOut(BaseModel):
    """Номер с корпоративной ценой — витрина подбора."""

    slug: str
    name: str
    shortName: str
    area: str
    capacity: int
    beds: str
    summary: str
    features: list[str]
    images: list[str]
    publicPrice: int
    corpPrice: int


class CorpBookingItemIn(BaseModel):
    roomSlug: str = Field(min_length=1, max_length=60)
    roomsCount: int = Field(default=1, ge=1, le=50)


class CorpBookingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    roomSlug: str = Field(validation_alias="room_slug")
    roomName: str = Field(default="", validation_alias="room_name")
    roomsCount: int = Field(default=1, validation_alias="rooms_count")
    pricePerNight: int = Field(default=0, validation_alias="price_per_night")
    amount: int = 0


class CorpBookingIn(BaseModel):
    checkIn: date
    checkOut: date
    adults: int = Field(default=1, ge=1, le=50)
    children: int = Field(default=0, ge=0, le=50)
    guestName: str = Field(default="", max_length=200)
    guestPhone: str = Field(default="", max_length=40)
    comment: str = Field(default="", max_length=2000)
    items: list[CorpBookingItemIn] = Field(min_length=1, max_length=20)

    @field_validator("checkOut")
    @classmethod
    def _after_check_in(cls, value: date, info):
        check_in = info.data.get("checkIn")
        if check_in and value <= check_in:
            raise ValueError("Дата выезда должна быть позже даты заезда")
        return value


class CorpBookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    hotelSlug: str = Field(default="airis", validation_alias="hotel_slug")
    checkIn: date = Field(validation_alias="check_in")
    checkOut: date = Field(validation_alias="check_out")
    nights: int
    adults: int
    children: int
    guestName: str = Field(default="", validation_alias="guest_name")
    guestPhone: str = Field(default="", validation_alias="guest_phone")
    comment: str = ""
    status: str
    totalAmount: int = Field(default=0, validation_alias="total_amount")
    invoiceNumber: str = Field(default="", validation_alias="invoice_number")
    createdAt: datetime = Field(validation_alias="created_at")
    cancelReason: str = Field(default="", validation_alias="cancel_reason")
    # Кто оформил — в таблице «Мои бронирования» есть колонка «Сотрудник».
    createdByName: str = ""
    items: list[CorpBookingItemOut] = []


class CorpCancelIn(BaseModel):
    reason: str = Field(default="", max_length=300)


class CompanyUserIn(BaseModel):
    """Заведение сотрудника. Пароль задаёт тот, кто заводит."""

    email: str = Field(min_length=3, max_length=160)
    fullName: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=40)
    role: str = Field(default="employee", pattern=r"^(admin|employee)$")
    password: str = Field(default="", max_length=200)


class CompanyUserPatch(BaseModel):
    fullName: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    role: str | None = Field(default=None, pattern=r"^(admin|employee)$")
    isActive: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class CompanyIn(BaseModel):
    """Создание компании из админки отеля."""

    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,58}$")
    name: str = Field(min_length=2, max_length=200)
    bin: str = Field(default="", max_length=12)
    contractNumber: str = Field(default="", max_length=60)
    contractDate: date | None = None
    paymentTerms: str = Field(default="", max_length=200)
    managerName: str = Field(default="", max_length=160)
    managerEmail: str = Field(default="", max_length=160)
    managerPhone: str = Field(default="", max_length=40)
    discountPercent: int = Field(default=0, ge=0, le=90)


class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    bin: str | None = Field(default=None, max_length=12)
    contractNumber: str | None = Field(default=None, max_length=60)
    contractDate: date | None = None
    paymentTerms: str | None = Field(default=None, max_length=200)
    managerName: str | None = Field(default=None, max_length=160)
    managerEmail: str | None = Field(default=None, max_length=160)
    managerPhone: str | None = Field(default=None, max_length=40)
    discountPercent: int | None = Field(default=None, ge=0, le=90)
    isActive: bool | None = None


class CompanyRateIn(BaseModel):
    roomSlug: str = Field(min_length=1, max_length=60)
    price: int = Field(ge=0, le=100_000_000)


class CompanyRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    roomSlug: str = Field(validation_alias="room_slug")
    price: int


class CorpBookingStatusIn(BaseModel):
    status: str = Field(pattern=r"^(new|confirmed|invoiced|paid|cancelled)$")
    invoiceNumber: str = Field(default="", max_length=60)
    reason: str = Field(default="", max_length=300)
