"""
Airis Residence API.

Запуск:  uvicorn app.main:app --reload
Docs:    http://localhost:8000/docs
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import check_credentials, create_token, require_admin
from .config import Settings, get_settings
from .db import Lead, Payment, Room, SessionLocal, get_session, init_db, utcnow
from .notify import notify_telegram
from .payments import PaymentError, get_provider, new_order_id
from .rooms_api import admin as rooms_admin_router, public as rooms_public_router
from .schemas import (
    LeadIn,
    LeadOut,
    LeadStatusIn,
    LoginIn,
    LoginOut,
    PaymentInitIn,
    PaymentInitOut,
)
from .seed_rooms import SEED_ROOMS, TRANSLATIONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


async def seed_rooms_if_empty() -> None:
    """
    Наполняет таблицу номеров один раз — при первом запуске.
    Если в базе уже что-то есть, не трогаем: правки из админки важнее.
    """
    async with SessionLocal() as session:
        existing = await session.execute(select(Room).limit(1))
        if existing.scalar_one_or_none() is not None:
            return

        for index, item in enumerate(SEED_ROOMS):
            session.add(
                Room(
                    slug=item["slug"],
                    name=item["name"],
                    short_name=item["short_name"],
                    price=item["price"],
                    area=item["area"],
                    capacity=item["capacity"],
                    beds=item["beds"],
                    summary=item["summary"],
                    description=item["description"],
                    features=item["features"],
                    images=item["images"],
                    translations=TRANSLATIONS.get(item["slug"], {}),
                    sort_order=index,
                    is_published=True,
                )
            )
        await session.commit()
        logger.info("Номера загружены в базу: %s шт.", len(SEED_ROOMS))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await seed_rooms_if_empty()
    logger.info(
        "Готово. Админка: %s, платежи: %s",
        "включена" if settings.admin_configured else "не настроена",
        settings.payment_provider or "не настроены",
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    description="Номера, заявки и приём онлайн-оплаты для отеля Airis Residence.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

# Загруженные из админки фотографии
app.mount("/media", StaticFiles(directory=str(settings.upload_path)), name="media")

app.include_router(rooms_public_router)
app.include_router(rooms_admin_router)


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Защита служебных эндпоинтов. Без заданного API_KEY они закрыты полностью."""
    if not settings.api_key or x_api_key != settings.api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный ключ доступа")


@app.get("/health", tags=["service"])
async def health():
    return {
        "status": "ok",
        "admin_configured": settings.admin_configured,
        "payments_configured": settings.payment_configured,
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }


# ────────────────────────── Вход в админку ──────────────────────────

_login_attempts: dict[str, list[float]] = {}


@app.post("/api/auth/login", response_model=LoginOut, tags=["admin: вход"])
async def login(
    payload: LoginIn, request: Request, cfg: Settings = Depends(get_settings)
):
    if not cfg.admin_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Админка не настроена: задайте ADMIN_PASSWORD и SECRET_KEY в .env",
        )

    # Простой тормоз против перебора: 10 попыток за 5 минут с одного адреса.
    import time

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    now = time.time()
    recent = [t for t in _login_attempts.get(ip, []) if now - t < 300]
    if len(recent) >= 10:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Слишком много попыток, подождите 5 минут"
        )
    recent.append(now)
    _login_attempts[ip] = recent

    if not check_credentials(cfg, payload.username, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")

    _login_attempts.pop(ip, None)
    token, expires_at = create_token(cfg, payload.username)
    return LoginOut(token=token, expiresAt=expires_at, username=payload.username)


@app.get("/api/admin/me", tags=["admin: вход"])
async def me(username: str = Depends(require_admin)):
    return {"username": username}


# ────────────────────────── Заявки ──────────────────────────


@app.post("/api/leads", status_code=201, tags=["leads"])
async def create_lead(
    payload: LeadIn,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Принимает заявку с сайта, кладёт в базу и шлёт уведомление."""
    # honeypot: заполнено — значит бот. Отвечаем успехом, чтобы он не подбирал обход.
    if payload.company:
        return {"ok": True}

    lead = Lead(
        name=payload.name.strip(),
        phone=payload.phone.strip(),
        email=(payload.email or "").strip() or None,
        check_in=payload.checkIn,
        check_out=payload.checkOut,
        adults=payload.adults,
        room=payload.room or None,
        comment=(payload.comment or "").strip() or None,
        ip=request.headers.get("x-forwarded-for", request.client.host if request.client else None),
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    background.add_task(notify_telegram, lead)
    return {"ok": True, "id": lead.id}


@app.get("/api/admin/leads", response_model=list[LeadOut], tags=["admin: заявки"])
async def admin_list_leads(
    limit: int = 100,
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_admin),
):
    """Список заявок для админки."""
    query = select(Lead).order_by(Lead.created_at.desc()).limit(min(limit, 500))
    if status_filter:
        query = query.where(Lead.status == status_filter)
    result = await session.execute(query)
    return list(result.scalars().all())


@app.patch("/api/admin/leads/{lead_id}", response_model=LeadOut, tags=["admin: заявки"])
async def admin_update_lead(
    lead_id: int,
    payload: LeadStatusIn,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_admin),
):
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Заявка не найдена")
    lead.status = payload.status
    await session.commit()
    await session.refresh(lead)
    return lead


@app.get("/api/leads", response_model=list[LeadOut], tags=["leads"], deprecated=True)
async def list_leads_by_key(
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_api_key),
):
    """Доступ к заявкам по X-API-Key — для интеграций, не для админки."""
    result = await session.execute(
        select(Lead).order_by(Lead.created_at.desc()).limit(min(limit, 500))
    )
    return list(result.scalars().all())


# ────────────────────────── Оплата ──────────────────────────


@app.post("/api/payments/init", response_model=PaymentInitOut, tags=["payments"])
async def init_payment(
    payload: PaymentInitIn,
    session: AsyncSession = Depends(get_session),
):
    """
    Создаёт платёж в банке и возвращает ссылку на оплату.

    Пока PAYMENT_* не заполнены — отвечает 501. Сайт в этом случае
    показывает оплату на месте, ничего не ломается.
    """
    provider = get_provider(settings)
    if provider is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Онлайн-оплата не подключена. Заполните PAYMENT_* в .env — см. docs/ИНТЕГРАЦИЯ.md",
        )

    order_id = new_order_id()
    payment = Payment(
        order_id=order_id,
        lead_id=payload.lead_id,
        amount=payload.amount * 100,  # храним в тиынах
        provider=provider.name,
        status="created",
    )
    session.add(payment)
    await session.commit()

    try:
        url = await provider.create_payment(
            order_id=order_id,
            amount_tenge=payload.amount,
            description=payload.description,
            email=payload.email,
            phone=payload.phone,
        )
    except PaymentError as exc:
        payment.status = "failed"
        await session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    payment.status = "pending"
    await session.commit()
    return PaymentInitOut(order_id=order_id, payment_url=url, status="pending")


@app.post("/api/payments/callback", tags=["payments"])
async def payment_callback(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Колбэк банка о результате оплаты (postLink / webhook).

    ⚠️ Именно этот адрес нужно передать банку:
        https://<домен-бэкенда>/api/payments/callback
    """
    provider = get_provider(settings)
    if provider is None:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Платёжный шлюз не подключён")

    body = await request.json()
    headers = {k.lower(): v for k, v in request.headers.items()}

    if not provider.verify_callback(body, headers):
        logger.warning("Колбэк с неверной подписью: %s", body)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Подпись не совпала")

    order_id, new_status = provider.parse_callback(body)
    if not order_id:
        raise HTTPException(400, "В колбэке нет номера заказа")

    result = await session.execute(select(Payment).where(Payment.order_id == order_id))
    payment = result.scalar_one_or_none()
    if payment is None:
        logger.error("Колбэк по неизвестному заказу %s", order_id)
        raise HTTPException(404, "Заказ не найден")

    payment.status = new_status
    payment.raw_callback = json.dumps(body, ensure_ascii=False)
    if new_status == "paid":
        payment.paid_at = utcnow()
        if payment.lead_id:
            lead = await session.get(Lead, payment.lead_id)
            if lead:
                lead.status = "confirmed"
    await session.commit()

    # Банки обычно ждут именно 200 с коротким телом.
    return {"ok": True}


@app.get("/api/payments/{order_id}", tags=["payments"])
async def payment_status(order_id: str, session: AsyncSession = Depends(get_session)):
    """Проверка статуса платежа — сайт опрашивает после возврата с оплаты."""
    result = await session.execute(select(Payment).where(Payment.order_id == order_id))
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(404, "Заказ не найден")
    return {
        "order_id": payment.order_id,
        "status": payment.status,
        "amount": payment.amount // 100,
        "currency": payment.currency,
        "paid_at": payment.paid_at,
    }
