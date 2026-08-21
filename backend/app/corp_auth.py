"""
Вход в корпоративный кабинет.

Чем это отличается от админки отеля (auth.py). Там одна учётная запись на
весь отель, логин с паролем лежат в окружении, и база пользователей была бы
лишней сложностью. Здесь пользователей много: несколько компаний, у каждой
несколько сотрудников, люди приходят и уходят. Поэтому таблица, хеши паролей
и проверка «жив ли ещё доступ» на каждом запросе.

Внешних библиотек по-прежнему нет. Пароли — PBKDF2 из стандартной библиотеки,
токен подписан HMAC-ом, сессии на сервере не хранятся.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

# Кодирование то же, что у админского токена: формат один, отличается только
# содержимое. Держать вторую копию base64-обвязки ради приличия — значит
# получить расхождение при первой же правке.
from .auth import _b64d, _b64e
from .config import Settings, get_settings
from .db import Company, CompanyUser, get_session

logger = logging.getLogger(__name__)

#: Имя куки. Отличается от админской (`airis_admin`) намеренно: сотрудник
#: компании и администратор отеля могут сидеть в одном браузере, и их сессии
#: не должны затирать друг друга.
COOKIE_NAME = "airis_corp"

#: Метка в токене. Без неё токен одного контура подошёл бы к другому:
#: подпись-то одним и тем же ключом. Проверяем явно.
TOKEN_TYPE = "corp"

# Стоимость подбора пароля. 240 тысяч раундов — порядок, рекомендованный
# OWASP для PBKDF2-SHA256; на входе это единицы миллисекунд, при переборе —
# годы. Число хранится внутри самого хеша, поэтому его можно поднять позже,
# не ломая уже заведённые пароли.
_PBKDF2_ROUNDS = 240_000
_ALGO = "pbkdf2_sha256"


# ─────────────────────────────── Пароли ───────────────────────────────


def hash_password(password: str) -> str:
    """Хеш в формате `алгоритм$раунды$соль$хеш` — всё нужное внутри строки."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"{_ALGO}${_PBKDF2_ROUNDS}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """
    Проверка пароля.

    Пустой или битый хеш — это «войти нельзя», а не ошибка: у только что
    заведённого сотрудника пароля ещё нет, и он не должен пускать никого.
    """
    try:
        algo, rounds, salt, digest = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if algo != _ALGO:
        return False
    try:
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _b64d(salt), int(rounds)
        )
        return hmac.compare_digest(expected, _b64d(digest))
    except Exception:
        return False


# ─────────────────────────────── Токен ────────────────────────────────


def create_token(settings: Settings, user: CompanyUser) -> tuple[str, int]:
    """Возвращает подписанный токен и момент истечения (unix-время)."""
    expires_at = int(time.time()) + settings.corp_session_hours * 3600
    payload = _b64e(
        json.dumps(
            {
                "typ": TOKEN_TYPE,
                "sub": user.id,
                "cid": user.company_id,
                "exp": expires_at,
            }
        ).encode()
    )
    signature = hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).digest()
    return f"{payload}.{_b64e(signature)}", expires_at


def verify_token(settings: Settings, token: str) -> dict | None:
    """Возвращает содержимое токена или None, если он битый, чужой или старый."""
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).digest()
    try:
        if not hmac.compare_digest(expected, _b64d(signature)):
            return None
        data = json.loads(_b64d(payload))
    except Exception:
        return None

    if data.get("typ") != TOKEN_TYPE:
        return None
    if int(data.get("exp", 0)) < time.time():
        return None
    return data


def _token_from(request: Request) -> str:
    """Токен из заголовка или из куки — как и в админке."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        if token:
            return token
    return request.cookies.get(COOKIE_NAME, "")


# ───────────────────────────── Зависимости ────────────────────────────


async def require_corp_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> CompanyUser:
    """
    Пускает сотрудника компании в закрытые эндпоинты.

    Токен подписан и содержит всё нужное, но пользователь всё равно читается
    из базы. Это осознанный лишний запрос: иначе отключённый сотрудник или
    компания с приостановленным договором продолжали бы работать до конца
    срока токена — то есть увольнение вступало бы в силу через полсуток.
    """
    if not settings.secret_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Корпоративный кабинет не настроен: задайте SECRET_KEY в .env",
        )

    token = _token_from(request)
    claims = verify_token(settings, token) if token else None
    if not claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нужно войти заново")

    user = await session.get(CompanyUser, int(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Доступ отключён")

    company = await session.get(Company, user.company_id)
    if company is None or not company.is_active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Доступ компании приостановлен — свяжитесь с менеджером Airis",
        )

    return user


async def require_corp_admin(
    user: CompanyUser = Depends(require_corp_user),
) -> CompanyUser:
    """Действия, доступные только ответственному в компании."""
    if user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Действие доступно только ответственному за корпоративный доступ",
        )
    return user
