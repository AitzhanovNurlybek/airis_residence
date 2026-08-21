"""
Вход в админку.

Одна учётная запись на отель — этого достаточно, отдельная база
пользователей тут была бы лишней сложностью. Логин и пароль лежат
в переменных окружения, токен подписывается HMAC-ом: без внешних
библиотек и без хранения сессий на сервере.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException, Request, status

from .config import Settings, get_settings


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


#: Метка контура в токене.
#:
#: Появилась не сразу и закрывает настоящую дыру. Корпоративный кабинет
#: подписывает свои токены тем же SECRET_KEY, а проверка ниже смотрела только
#: на то, что `sub` непустой. У корпоративного токена `sub` — это id
#: сотрудника, то есть строка «1»: любой сотрудник любой компании проходил
#: в админку отеля. Теперь контур указан явно и сверяется.
TOKEN_TYPE = "admin"


def create_token(settings: Settings, username: str) -> tuple[str, int]:
    """Возвращает подписанный токен и момент его истечения (unix-время)."""
    expires_at = int(time.time()) + settings.session_hours * 3600
    payload = _b64e(
        json.dumps({"typ": TOKEN_TYPE, "sub": username, "exp": expires_at}).encode()
    )
    signature = hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).digest()
    return f"{payload}.{_b64e(signature)}", expires_at


def verify_token(settings: Settings, token: str) -> str | None:
    """Возвращает имя пользователя или None, если токен битый/просрочен."""
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

    # Токены, выпущенные до появления метки, ещё живут в браузерах — их
    # не отвергаем, иначе администратор вылетит посреди работы. Чужую метку
    # (корпоративную) отвергаем всегда.
    if data.get("typ", TOKEN_TYPE) != TOKEN_TYPE:
        return None
    if int(data.get("exp", 0)) < time.time():
        return None
    return str(data.get("sub", ""))


def check_credentials(settings: Settings, username: str, password: str) -> bool:
    """Сравнение в постоянном времени — чтобы нельзя было подобрать по задержке."""
    user_ok = secrets.compare_digest(username.strip(), settings.admin_username)
    pass_ok = secrets.compare_digest(password, settings.admin_password)
    return user_ok and pass_ok


def require_admin(
    request: Request, settings: Settings = Depends(get_settings)
) -> str:
    """Зависимость для всех эндпоинтов админки."""
    if not settings.admin_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Админка не настроена: задайте ADMIN_PASSWORD и SECRET_KEY в .env",
        )

    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        token = request.cookies.get("airis_admin", "")

    username = verify_token(settings, token) if token else None
    # Вторая проверка, независимая от метки: учётка в админке ровно одна, и
    # её имя задано в окружении. Токен с любым другим `sub` — не наш.
    if not username or not secrets.compare_digest(username, settings.admin_username):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нужно войти заново")
    return username
