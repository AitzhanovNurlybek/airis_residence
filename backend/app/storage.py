"""
Хранилище фотографий.

Две реализации за одним интерфейсом:

  · LocalStorage — файлы на диске. Так работает локальная разработка
    и любой обычный сервер.
  · S3Storage — объектное хранилище (Supabase Storage, Cloudflare R2,
    AWS S3, MinIO). Нужно там, где диска нет или он одноразовый:
    на Vercel записать файл попросту некуда.

Какая именно включится, решают переменные окружения: заданы S3_* —
работает S3, не заданы — диск. Код, который вызывает хранилище,
об этом не знает.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import HTTPException, status

from .config import Settings

logger = logging.getLogger(__name__)


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str) -> str:
        """Сохраняет файл и возвращает публичную ссылку на него."""

    @abstractmethod
    def delete(self, url: str) -> None:
        """Удаляет файл по ранее выданной ссылке. Чужие ссылки игнорирует."""


class LocalStorage(Storage):
    """Файлы на диске, отдаются FastAPI через StaticFiles на /media."""

    marker = "/media/"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def save(self, key: str, data: bytes, content_type: str) -> str:
        target = self.settings.upload_path / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        base = self.settings.public_media_base.rstrip("/")
        return f"{base}/media/{key}" if base else f"/media/{key}"

    def delete(self, url: str) -> None:
        if self.marker not in url:
            return
        relative = url.split(self.marker, 1)[1]
        target = (self.settings.upload_path / relative).resolve()

        # Защита от «../»: путь обязан остаться внутри папки загрузок
        if not str(target).startswith(str(self.settings.upload_path)):
            logger.warning("Попытка удалить файл вне папки загрузок: %s", url)
            return
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Не удалось удалить %s: %s", target, exc)


class S3Storage(Storage):
    """
    Любое S3-совместимое хранилище.

    Проверено на Supabase Storage и Cloudflare R2 — у обоих S3-протокол.
    Отличаются только адрес эндпоинта и формат публичной ссылки, поэтому
    и то и другое настраивается переменными окружения.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Для S3-хранилища нужен boto3: pip install -r requirements.txt"
            ) from exc

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket

    def _public_url(self, key: str) -> str:
        base = settings_public_base(self.settings)
        return f"{base}/{key}"

    def save(self, key: str, data: bytes, content_type: str) -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                # Год в кэше: имя файла содержит случайный хеш, старое
                # содержимое по тому же адресу не появится.
                CacheControl="public, max-age=31536000, immutable",
            )
        except Exception as exc:
            logger.exception("Не удалось загрузить %s в хранилище", key)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Хранилище не приняло файл. Проверьте настройки S3_*.",
            ) from exc
        return self._public_url(key)

    def delete(self, url: str) -> None:
        base = settings_public_base(self.settings)
        if not url.startswith(base):
            # Ссылка не из нашего хранилища (например, фото из первой
            # поставки, лежащее во фронтенде) — просто убираем её из списка.
            return
        key = url[len(base) :].lstrip("/")
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception:
            logger.exception("Не удалось удалить %s из хранилища", key)


def settings_public_base(settings: Settings) -> str:
    """
    Адрес, по которому файлы видны снаружи.

    У Supabase и R2 он отличается от адреса API, поэтому задаётся
    отдельно через S3_PUBLIC_BASE.
    """
    if settings.s3_public_base:
        return settings.s3_public_base.rstrip("/")
    endpoint = (settings.s3_endpoint or "").rstrip("/")
    return f"{endpoint}/{settings.s3_bucket}"


def get_storage(settings: Settings) -> Storage:
    if settings.s3_configured:
        return S3Storage(settings)
    return LocalStorage(settings)
