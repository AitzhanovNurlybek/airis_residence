"""Настройки бэкенда. Всё читается из окружения — секретов в коде нет."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Airis Residence API"
    debug: bool = False

    # Внешний префикс, под которым доступен бэкенд.
    # На Vercel это /api/backend (см. vercel.json). Локально — пусто.
    root_path: str = ""

    # SQLite для локальной разработки.
    # В облаке: postgresql+asyncpg://user:pass@host/db
    # ⚠️ Брать строку подключения ЧЕРЕЗ ПУЛЕР (у Neon и Supabase это
    #    отдельный адрес с -pooler), иначе serverless выест лимит соединений.
    database_url: str = "sqlite+aiosqlite:///./airis.db"
    # Облачные Postgres требуют TLS; для своего сервера можно выключить.
    database_ssl: bool = True

    # Домены фронтенда, которым разрешён доступ к API
    cors_origins: str = "http://localhost:3000,https://airisresidence.kz,https://www.airisresidence.kz"

    # Ключ, которым фронтенд/админка подписывают запросы к закрытым эндпоинтам
    api_key: str = ""

    # ─── Вход в админку ────────────────────────────────────────────────
    admin_username: str = "admin"
    admin_password: str = ""          # пусто — вход закрыт
    secret_key: str = ""              # длинная случайная строка для подписи токена
    session_hours: int = 12

    # ─── Корпоративный кабинет ─────────────────────────────────────────
    # Учётные записи компаний лежат в базе (см. corp_auth), здесь только
    # срок сессии. Он длиннее админского: сотрудник компании работает в
    # кабинете весь день, и разлогин посреди оформления брони — это
    # потерянная заявка, а не безопасность.
    corp_session_hours: int = 24

    # ─── Загрузка фотографий ───────────────────────────────────────────
    upload_dir: str = "./media"
    # Публичный адрес, по которому отдаются загруженные файлы (для диска).
    public_media_base: str = ""
    max_upload_mb: int = 15
    # Фото ужимаются до этой ширины — оригиналы с телефона по 6 МБ
    # убивают скорость сайта и место на диске.
    image_max_width: int = 2200

    # ─── Видеообзоры номеров ───────────────────────────────────────────
    # Ролик грузится браузером напрямую в хранилище, поэтому лимит Vercel
    # (4.5 МБ на запрос к функции) здесь не мешает. Но трафик хранилища
    # не бесплатен: на free-тарифе Supabase это 5 ГБ в месяц, а значит
    # длинный ролик в высоком качестве съест его за пару сотен просмотров.
    max_video_mb: int = 40

    # ─── S3-совместимое хранилище ──────────────────────────────────────
    # Заполняется, когда диска нет: на Vercel и других serverless-площадках
    # записать файл некуда. Подходит Supabase Storage, Cloudflare R2, AWS S3.
    # Пусто — фотографии сохраняются на диск, как обычно.
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "auto"
    # Адрес, по которому файлы видны снаружи. У Supabase и R2 он отличается
    # от адреса API, поэтому задаётся отдельно.
    s3_public_base: str = ""

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

    # ─── ИИ-консьерж (WhatsApp, Instagram, сайт) ───────────────────────
    # Факты об отеле консьерж не хранит у себя: он берёт их с /api/knowledge
    # фронтенда, где они собираются из тех же модулей, что рисуют страницы.
    # Своя копия прайса рано или поздно отстаёт от админки, а консьерж
    # называет цену гостю от лица отеля — расхождение здесь дороже лишнего
    # сетевого запроса.
    site_url: str = "https://airisresidence.kz"
    # Сколько держать факты в памяти функции. Цены меняют не каждый час,
    # а ходить за ними на каждое сообщение — лишняя секунда в ответе.
    knowledge_ttl_seconds: int = 600

    anthropic_api_key: str = ""
    concierge_model: str = "claude-sonnet-5"
    # Предел на ответ. Консьерж в мессенджере пишет коротко: длинную простыню
    # в WhatsApp не читают, а токены она жжёт на каждом сообщении.
    concierge_max_tokens: int = 700
    # Сколько прошлых сообщений диалога подкладывать в запрос.
    concierge_history_depth: int = 12

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
    def s3_configured(self) -> bool:
        return bool(self.s3_bucket and self.s3_access_key and self.s3_secret_key)

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
