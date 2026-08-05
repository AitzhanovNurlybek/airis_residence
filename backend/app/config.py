"""Настройки бэкенда. Всё читается из окружения — секретов в коде нет."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Airis Residence API"
    debug: bool = False

    # SQLite для старта; для продакшена подставить postgresql+asyncpg://...
    database_url: str = "sqlite+aiosqlite:///./airis.db"

    # Домены фронтенда, которым разрешён доступ к API
    cors_origins: str = "http://localhost:3000,https://airisresidence.kz,https://www.airisresidence.kz"

    # Ключ, которым фронтенд/админка подписывают запросы к закрытым эндпоинтам
    api_key: str = ""

    # ─── Вход в админку ────────────────────────────────────────────────
    admin_username: str = "admin"
    admin_password: str = ""          # пусто — вход закрыт
    secret_key: str = ""              # длинная случайная строка для подписи токена
    session_hours: int = 12

    # ─── Загрузка фотографий ───────────────────────────────────────────
    upload_dir: str = "./media"
    # Публичный адрес, по которому отдаются загруженные файлы.
    # Обязателен в проде: без него ссылки будут относительными.
    public_media_base: str = ""
    max_upload_mb: int = 15
    # Фото ужимаются до этой ширины — оригиналы с телефона по 6 МБ
    # убивают скорость сайта и место на диске.
    image_max_width: int = 2200

    # Уведомления о заявках
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ─── Платёжный шлюз ────────────────────────────────────────────────
    # Заполняется данными, которые выдаст банк. Пока пусто —
    # эндпоинт оплаты честно отвечает «не настроено».
    payment_provider: str = ""          # epay_halyk | fortebank | none
    payment_terminal_id: str = ""
    payment_client_id: str = ""
    payment_client_secret: str = ""
    payment_base_url: str = ""          # адрес API банка
    payment_success_url: str = "https://airisresidence.kz/oplata/uspeh"
    payment_failure_url: str = "https://airisresidence.kz/oplata/oshibka"
    payment_webhook_secret: str = ""    # для проверки подписи колбэка

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def payment_configured(self) -> bool:
        return bool(self.payment_provider and self.payment_base_url and self.payment_client_id)

    @property
    def admin_configured(self) -> bool:
        return bool(self.admin_password and self.secret_key)

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
