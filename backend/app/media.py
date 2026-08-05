"""
Приём фотографий из админки.

Каждый загруженный файл пережимается: телефоны отдают кадры по 5–8 МБ,
а на сайте такое фото — это секунды ожидания у гостя и лишние гигабайты
на диске. Храним WebP шириной не больше settings.image_max_width.
"""

import io
import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from .config import Settings

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _safe_folder(settings: Settings, slug: str) -> Path:
    """Папка номера внутри media/. Slug проверен схемой, но бережёного бог бережёт."""
    clean = "".join(ch for ch in slug if ch.isalnum() or ch in "-_")[:60]
    if not clean:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный код номера")
    folder = settings.upload_path / "rooms" / clean
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def public_url(settings: Settings, relative: str) -> str:
    """Ссылка, по которой фото увидит сайт."""
    base = settings.public_media_base.rstrip("/")
    return f"{base}/media/{relative}" if base else f"/media/{relative}"


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

    folder = _safe_folder(settings, slug)
    filename = f"{uuid.uuid4().hex[:16]}.webp"
    image.save(folder / filename, "WEBP", quality=82, method=5)

    return public_url(settings, f"rooms/{folder.name}/{filename}")


def delete_room_image(settings: Settings, url: str) -> None:
    """
    Удаляет файл с диска, если ссылка ведёт в нашу папку media/.
    Фото из первоначальной поставки (`/images/...`) лежат во фронтенде —
    их не трогаем, просто убираем ссылку из списка.
    """
    marker = "/media/rooms/"
    if marker not in url:
        return

    relative = url.split(marker, 1)[1]
    target = (settings.upload_path / "rooms" / relative).resolve()

    # Защита от «../»: путь обязан остаться внутри media/
    if not str(target).startswith(str(settings.upload_path)):
        logger.warning("Попытка удалить файл вне media/: %s", url)
        return

    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Не удалось удалить %s: %s", target, exc)
