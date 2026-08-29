"""Настройки бэкенда. Всё читается из окружения — секретов в коде нет."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

# Часовой пояс отеля берём из almaty: он ничего из проекта не импортирует,
# поэтому кольца не возникает, а второе определение того же пояса рано или
# поздно разъехалось бы с первым.
from .almaty import HOTEL_TZ

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
    payment_webhook_secret: str = ""

    #: Секретное слово мерчанта. У FreedomPay им подписывается каждый запрос
    #: и каждое уведомление — отдельного токена там нет.
    payment_client_secret: str = ""
    #: Куда банк присылает результат. Отличается от success_url: тот для
    #: браузера гостя, этот — для сервера, и гость его не видит.
    payment_result_url: str = "https://airisresidence.kz/api/backend/api/payments/result"
    #: Тестовый режим банка: платежи проходят без списания денег.
    payment_testing: bool = True    # для проверки подписи колбэка

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

    # ─── WhatsApp через Green API ──────────────────────────────────────
    # console.green-api.com → создать инстанс → отсканировать QR телефоном
    # отеля → скопировать сюда. Пусто — канал не запускается.
    green_api_id: str = ""
    green_api_token: str = ""

    #: Секрет вебхука WhatsApp. Адрес приёмника открыт всему интернету, а по
    #: нему отвечают гостям от лица отеля — без секрета писать от нашего
    #: имени смог бы кто угодно.
    whatsapp_webhook_secret: str = ""

    # ─── Распознавание голосовых сообщений ───
    #
    # Гость в WhatsApp часто говорит, а не пишет. Без распознавания консьерж
    # честно просит написать текстом, но часть людей просто уходит. Ключ
    # включает расшифровку; без него всё работает как раньше.
    #
    # Голос гостя при этом уходит третьей стороне — поэтому включается только
    # явно, заполненным ключом, а не «по умолчанию, если получится».
    speech_api_key: str = ""
    #: Адрес совместимой службы. По умолчанию OpenAI; можно заменить на
    #: любую, говорящую в том же формате, не трогая код.
    speech_api_url: str = "https://api.openai.com/v1/audio/transcriptions"
    #: gpt-4o-mini-transcribe точнее старого whisper-1 и дешевле крупных.
    speech_model: str = "gpt-4o-mini-transcribe"
    #: Подсказка языка заметно поднимает точность на коротких записях.
    speech_language: str = "ru"
    #: Предел размера записи. Гость может зажать кнопку и прислать десять
    #: минут; дешевле попросить написать текстом, чем оплатить случайность.
    speech_max_mb: int = 8
    # Пауза между отправками, секунды. Против блокировки номера: WhatsApp
    # плохо относится к номерам, которые отвечают мгновенно и без остановки.
    # Первую неделю нового номера лучше держать больше.
    whatsapp_send_delay: float = 2.0
    # Сколько ждать сообщение в одном опросе очереди.
    whatsapp_poll_seconds: int = 20

    # ─── Система бронирования отеля ────────────────────────────────────
    # Пусто — не подключена: наличие номеров подтверждает менеджер вручную,
    # и всё, что показывает наличие гостю, честно об этом говорит.
    # `stub`  — локальная заглушка для отладки консьержа. НЕ для боевого сайта:
    #           занятость она выдумывает, пусть и воспроизводимо.
    # `exely` — настоящая система, когда интеграторы отдадут доступ.
    booking_system: str = ""
    exely_base_url: str = ""
    exely_api_key: str = ""
    exely_hotel_code: str = "509506"

    # Доступ к официальному API Exely (OAuth 2.0). Выдаётся в кабинете:
    # Настройки гостиницы → Подключения API → Создать подключение. Там же
    # показываются адреса — подставлять их наугад нельзя, поэтому значений
    # по умолчанию тут нет: пустое поле честно означает «не подключено».
    #
    # propertyId — «Property ID» в документации Exely. Совпадает ли он с
    # кодом отеля 509506 из виджета — не подтверждено: в примерах
    # документации это просто произвольное число (1024, 7291). Дешевле всего
    # проверить: exely_check.py сразу покажет 200 или 404.
    exely_client_id: str = ""
    exely_client_secret: str = ""
    exely_property_id: str = ""
    exely_auth_url: str = ""
    exely_api_base: str = ""

    #: Секрет вебхука. Адрес приёмника открыт всему интернету, и без секрета
    #: точка не работает вовсе: писать в базу отеля должен только Exely.
    exely_webhook_secret: str = ""

    @property
    def exely_api_ready(self) -> bool:
        """Есть ли всё, чтобы ходить в официальное API Exely."""
        return all((
            self.exely_client_id,
            self.exely_client_secret,
            self.exely_property_id,
            self.exely_auth_url,
            self.exely_api_base,
        ))

    anthropic_api_key: str = ""
    concierge_model: str = "claude-sonnet-5"
    # Предел на ответ. Консьерж в мессенджере пишет коротко: длинную простыню
    # в WhatsApp не читают, а токены она жжёт на каждом сообщении.
    concierge_max_tokens: int = 700
    # Сколько прошлых сообщений диалога подкладывать в запрос.
    concierge_history_depth: int = 12

    # С какого момента дожимать оборванные разговоры. Пустое значение —
    # не дожимать вовсе, и это нарочно значение по умолчанию: включать
    # рассылку гостям молча, одним лишь выкладыванием кода, нельзя.
    #
    # Дата нужна ещё и потому, что в базе лежат прошлые переписки — тестовые
    # и просто старые. Без границы первый же запуск написал бы всем сразу,
    # разом превратив аккуратную функцию в рассылку. Учитываются только
    # разговоры, где гость написал ПОЗЖЕ этого момента.
    #
    # Формат: 2026-08-30 или 2026-08-30T09:00. Время алматинское.
    followup_since: str = ""

    # Через сколько часов тишины писать вдогонку и когда прощаться. Вынесено
    # в настройки, чтобы отель мог сделать бота сдержаннее без правки кода:
    # «навязчиво» — вопрос вкуса владельца, а не программиста.
    followup_after_hours: int = 2
    followup_final_hours: int = 24

    @property
    def followup_from(self) -> datetime | None:
        """Момент, раньше которого разговоры не трогаем. None — дожим выключен."""
        raw = (self.followup_since or "").strip()
        if not raw:
            return None
        try:
            moment = datetime.fromisoformat(raw)
        except ValueError:
            return None
        # Без часового пояса считаем алматинским: именно так его напишет
        # человек, а сравнивать придётся с UTC из базы.
        return moment.replace(tzinfo=HOTEL_TZ) if moment.tzinfo is None else moment

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
