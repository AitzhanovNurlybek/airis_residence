"""
Приём фотографий из админки.

Каждый загруженный файл пережимается: телефоны отдают кадры по 5–8 МБ,
а на сайте такое фото — это секунды ожидания у гостя и лишние гигабайты
в хранилище. Храним WebP шириной не больше settings.image_max_width.

Куда именно ложится результат — на диск или в S3 — решает storage.py.
Здесь только обработка изображения.
"""

import io
import logging
import uuid

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from .config import Settings
from .storage import get_storage

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _safe_slug(slug: str) -> str:
    clean = "".join(ch for ch in slug if ch.isalnum() or ch in "-_")[:60]
    if not clean:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный код номера")
    return clean


async def save_room_image(settings: Settings, slug: str, upload: UploadFile) -> str:
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Формат {upload.content_type or 'неизвестный'} не поддерживается. "
            "Загрузите JPG, PNG или WebP.",
        )

    raw = await upload.read()
    limit = settings.max_upload_mb * 1024 * 1024
    if len(raw) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Файл больше {settings.max_upload_mb} МБ",
        )

    try:
        image = Image.open(io.BytesIO(raw))
        # Учитываем EXIF-поворот: иначе снятое телефоном фото ляжет боком.
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
    except Exception as exc:
        logger.warning("Не удалось прочитать изображение: %s", exc)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Файл не похож на изображение"
        ) from exc

    if image.width > settings.image_max_width:
        ratio = settings.image_max_width / image.width
        new_size = (settings.image_max_width, max(1, round(image.height * ratio)))
        image = image.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=82, method=5)

    key = f"rooms/{_safe_slug(slug)}/{uuid.uuid4().hex[:16]}.webp"
    return get_storage(settings).save(key, buffer.getvalue(), "image/webp")


def delete_room_image(settings: Settings, url: str) -> None:
    """
    Убирает файл из хранилища.

    Фотографии из первоначальной поставки (`/images/...`) лежат во
    фронтенде — их не трогаем, просто убираем ссылку из списка.
    """
    if url.startswith("/images/"):
        return
    get_storage(settings).delete(url)
