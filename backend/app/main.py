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
from .corp_api import admin as corp_admin_router, corp as corp_router
from .local_api import router as local_router
from .rooms_api import admin as rooms_admin_router, public as rooms_public_router
from .site_videos_api import (
    admin as site_videos_admin_router,
    public as site_videos_public_router,
)
from .schemas import (
    LeadIn,
    LeadOut,
    LeadStatusIn,
    LoginIn,
    LoginOut,
    PaymentInitIn,
    PaymentInitOut,
)
from .seed_rooms import SEED_ROOMS
from .throttle import (
    ADMIN_ATTEMPTS,
    ADMIN_BLOCK_SECONDS,
    client_ip,
    reset,
    seconds_left,
)

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
                    sort_order=index,
                    is_published=True,
                )
            )
        await session.commit()
        logger.info("Номера загружены в базу: %s шт.", len(SEED_ROOMS))


_initialised = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    # В serverless этот код выполняется при каждом холодном старте.
    # Флаг избавляет от лишней работы, пока экземпляр живой.
    global _initialised
    if not _initialised:
        await init_db()
        await seed_rooms_if_empty()
        _initialised = True
        logger.info(
            "Готово. Хранилище: %s, админка: %s, платежи: %s",
            "S3" if settings.s3_configured else "диск",
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

class StripPrefixMiddleware:
    """
    Убирает внешний префикс из пути запроса.

    На Vercel бэкенд живёт под адресом /api/backend/... — так настроен
    rewrite в vercel.json. Дойдёт ли до приложения полный путь или уже
    обрезанный, зависит от площадки, а гадать здесь нельзя: ошибка даст
    молчаливый 404 на всех эндпоинтах.

    Поэтому обрезаем сами и только если префикс действительно есть.
    Локально ROOT_PATH пустой и middleware ничего не делает.
    """

    def __init__(self, app, prefix: str) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.prefix:
            path = scope.get("path", "")
            if path.startswith(self.prefix):
                trimmed = path[len(self.prefix) :] or "/"
                scope = {**scope, "path": trimmed, "raw_path": trimmed.encode()}
        await self.app(scope, receive, send)


if settings.root_path:
    app.add_middleware(StripPrefixMiddleware, prefix=settings.root_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

# Фотографии с диска отдаём сами. Когда включено S3, файлы раздаёт
# хранилище, а на serverless-площадках папки для них попросту нет —
# обращаться к upload_path в этом случае нельзя, он пытается её создать.
if not settings.s3_configured:
    app.mount("/media", StaticFiles(directory=str(settings.upload_path)), name="media")

app.include_router(rooms_public_router)
app.include_router(rooms_admin_router)
app.include_router(site_videos_public_router)
app.include_router(site_videos_admin_router)
# Корпоративный кабинет: /api/corp/* для компаний, /api/admin/corp/* для отеля
app.include_router(corp_router)
app.include_router(corp_admin_router)

# Отладочная оснастка: локальная шахматка и окно переписки с консьержем.
# Уйдёт вместе с шахматкой, когда подключим настоящий Exely.
app.include_router(local_router)


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


@app.post("/api/auth/login", response_model=LoginOut, tags=["admin: вход"])
async def login(
    payload: LoginIn, request: Request, cfg: Settings = Depends(get_settings)
):
    if not cfg.admin_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Админка не настроена: задайте ADMIN_PASSWORD и SECRET_KEY в .env",
        )

    # Три попытки, потом час. Учётка одна и логин известен, поэтому строго.
    key = f"admin:{client_ip(request)}"
    wait = seconds_left(key, ADMIN_ATTEMPTS, ADMIN_BLOCK_SECONDS)
    if wait:
        minutes = max(1, round(wait / 60))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Три неудачных попытки подряд. Вход заблокирован, осталось "
            f"около {minutes} мин. Если ждать нельзя — перезапустите приложение "
            f"на Vercel (Redeploy), счётчик обнулится.",
        )

    if not check_credentials(cfg, payload.username, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")

    reset(key)
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


@app.delete("/api/admin/leads/{lead_id}", status_code=204, tags=["admin: заявки"])
async def admin_delete_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_admin),
):
    """
    Удаление заявки.

    Нужно для мусора: проверок формы при запуске и спама от ботов. Настоящую
    заявку удалять не стоит даже отменённую — по ней потом восстанавливают,
    кто звонил и о чём договорились. Для «не поедет» есть статус «Отменена»,
    он оставляет след.
    """
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Заявка не найдена")
    await session.delete(lead)
    await session.commit()
    logger.info("Удалена заявка #%s (%s)", lead_id, lead.name)


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
