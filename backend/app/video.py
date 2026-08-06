"""
Видеообзоры номеров.

В отличие от фотографий, ролик не проходит через наш сервер: у Vercel
запрос к функции ограничен 4.5 МБ, а видео заведомо больше. Поэтому:

  1. админка просит у нас временную ссылку (`build_upload`);
  2. браузер грузит файл по ней прямо в хранилище;
  3. админка сообщает, что закончила, и мы проверяем результат
     (`verify_uploaded`) — размер и тип берём у хранилища, а не со слов
     клиента, потому что до этого момента файл нам не подконтролен.

Если хранилище не умеет временные ссылки (обычный диск на своём
сервере), `build_upload` вернёт None, и админка загрузит ролик
привычным способом — через API.
"""

import logging
import uuid

from fastapi import HTTPException, status

from .config import Settings
from .storage import get_storage

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    # Так отдаёт видео айфон. Браузеры такой файл обычно играют,
    # но лучше предупредить владельца и попросить mp4.
    "video/quicktime": "mov",
}


def _safe_slug(slug: str) -> str:
    clean = "".join(ch for ch in slug if ch.isalnum() or ch in "-_")[:60]
    if not clean:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный код номера")
    return clean


def _check_type(content_type: str) -> str:
    ext = ALLOWED_TYPES.get(content_type)
    if not ext:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Поддерживаются MP4, WebM и MOV. Лучше всего MP4 — его играют все браузеры.",
        )
    return ext


def _check_size(settings: Settings, size: int) -> None:
    limit = settings.max_video_mb * 1024 * 1024
    if size > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Ролик больше {settings.max_video_mb} МБ. "
            "Сожмите его или снимите короче: длинное видео гость всё равно не досмотрит, "
            "а трафик хранилища расходуется на каждый просмотр.",
        )


def new_key(slug: str, content_type: str) -> str:
    """Имя файла в хранилище. Случайный хвост — чтобы старый ролик
    не подменялся новым по тому же адресу и не залипал в кэше."""
    ext = _check_type(content_type)
    return f"rooms/{_safe_slug(slug)}/video-{uuid.uuid4().hex[:16]}.{ext}"


def build_upload(
    settings: Settings, slug: str, content_type: str, size: int
) -> tuple[str, str] | None:
    """Ключ и временная ссылка на загрузку. None — хранилище так не умеет."""
    _check_size(settings, size)
    key = new_key(slug, content_type)

    url = get_storage(settings).signed_upload(key, content_type)
    return (key, url) if url else None


def verify_uploaded(settings: Settings, slug: str, key: str) -> str:
    """
    Проверяет реально загруженный файл и возвращает публичную ссылку.

    Клиенту на слово не верим: ключ он мог прислать любой, а размер
    подписью не ограничен. Ошибочный файл сразу убираем из хранилища,
    чтобы не копить мусор, за который платит владелец.
    """
    storage = get_storage(settings)

    if not key.startswith(f"rooms/{_safe_slug(slug)}/video-"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ссылка не от этого номера")

    found = storage.stat(key)
    if not found:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Файл не дошёл до хранилища. Попробуйте загрузить ещё раз.",
        )

    size, content_type = found
    try:
        _check_type(content_type)
        _check_size(settings, size)
    except HTTPException:
        storage.delete(storage.public_url(key))
        raise

    return storage.public_url(key)


async def save_video_through_api(settings: Settings, slug: str, upload) -> str:
    """
    Обычная загрузка — файл идёт через нас.

    Работает на своём сервере и локально. На Vercel сюда пролезет только
    ролик меньше 4.5 МБ, поэтому основной путь всё-таки временная ссылка.
    """
    content_type = upload.content_type or ""
    _check_type(content_type)

    raw = await upload.read()
    _check_size(settings, len(raw))

    key = new_key(slug, content_type)
    return get_storage(settings).save(key, raw, content_type)


def delete_video(settings: Settings, url: str) -> None:
    if not url:
        return
    get_storage(settings).delete(url)
