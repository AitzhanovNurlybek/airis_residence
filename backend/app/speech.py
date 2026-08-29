"""
Расшифровка голосовых сообщений гостя.

Claude голос не слышит, поэтому нужна отдельная служба. Здесь она одна —
совместимая с форматом OpenAI `POST /v1/audio/transcriptions`, но адрес
вынесен в настройки: тот же код работает с любым поставщиком, говорящим на
этом же диалекте, и переезд не потребует правок.

Что здесь решается, кроме собственно распознавания.

**Голос гостя уходит третьей стороне.** Это не то же самое, что отправить
туда прайс отеля: в голосовом может прозвучать что угодно, вплоть до
номера карты. Поэтому распознавание включается только явно — заполненным
ключом, а не «по умолчанию, если получится».

**Длинное аудио стоит денег и времени.** Гость может прислать десять минут,
случайно зажав кнопку. Файл больше разрешённого размера не отправляем вовсе:
дешевле попросить написать текстом, чем оплатить чужую случайность.

**Отказ не должен превращаться в тишину.** Если служба не ответила, гость
всё равно получает ответ — просьбу написать текстом. Молчание в переписке
воспринимается как игнорирование, и это худшее из возможного.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: Сколько ждать распознавание. Минута аудио расшифровывается за секунды,
#: но у службы бывают всплески; при этом весь ответ гостю должен уложиться
#: в время жизни функции, поэтому запас умеренный.
TIMEOUT = 40.0

#: Как узнать формат записи по её первым байтам. Ключ — сигнатура, значение —
#: расширение и тип содержимого.
#:
#: Зачем это вообще. Служба распознавания определяет формат ПО ИМЕНИ ФАЙЛА и
#: отказывает, если расширение ей незнакомо. WhatsApp называет голосовые
#: `.oga`, и живое сообщение гостя получило ровно это: «Unsupported file
#: format oga» — при том что внутри обычный OGG, который служба принимает под
#: именем `.ogg`. Гость в ответ увидел «голосовые пока не распознаю», хотя
#: распознавание было включено и работало.
#:
#: Полагаться на имя, пришедшее от мессенджера, больше нельзя: оно описывает
#: не формат, а привычку конкретного отправителя. Смотрим в сами байты.
SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"OggS", "ogg", "audio/ogg"),
    (b"RIFF", "wav", "audio/wav"),
    (b"ID3", "mp3", "audio/mpeg"),
    (b"fLaC", "flac", "audio/flac"),
    (bytes([0x1A, 0x45, 0xDF, 0xA3]), "webm", "audio/webm"),
)

#: Чем назвать запись, если сигнатура незнакома. `.mp3` — самый вероятный
#: формат из тех, что служба принимает, и осмысленнее, чем чужое `.oga`.
FALLBACK_FORMAT = ("mp3", "audio/mpeg")


def _format(audio: bytes) -> tuple[str, str]:
    """Расширение и тип содержимого — по первым байтам записи."""
    head = audio[:16]
    for signature, extension, mime in SIGNATURES:
        if head.startswith(signature):
            return extension, mime
    # MP3 без тега ID3 начинается с кадрового заголовка.
    if head[:2] in (bytes([0xFF, 0xFB]), bytes([0xFF, 0xF3]), bytes([0xFF, 0xF2])):
        return "mp3", "audio/mpeg"
    # MP4 и M4A: сигнатура смещена на четыре байта.
    if audio[4:8] == b"ftyp":
        return "m4a", "audio/mp4"
    return FALLBACK_FORMAT


class SpeechUnavailable(RuntimeError):
    """Распознать не вышло. Гостю ответим текстом, а не молчанием."""


def configured(settings: Any) -> bool:
    """Включено ли распознавание.

    Нужен именно ключ: адрес и модель имеют разумные значения по умолчанию,
    а ключ по умолчанию быть не может.
    """
    return bool(getattr(settings, "speech_api_key", ""))


async def transcribe(settings: Any, audio: bytes, filename: str = "voice.oga") -> str:
    """Превратить голосовое в текст.

    Возвращает распознанную речь. Пустая строка означает, что в записи не
    разобрали ни слова — это не ошибка, так бывает с тишиной и шумом.
    """
    if not configured(settings):
        raise SpeechUnavailable("Распознавание речи не настроено")

    limit = int(getattr(settings, "speech_max_mb", 8) or 8) * 1024 * 1024
    if len(audio) > limit:
        raise SpeechUnavailable(
            f"Запись слишком длинная: {len(audio) // 1024 // 1024} МБ при пределе "
            f"{limit // 1024 // 1024} МБ"
        )
    if not audio:
        raise SpeechUnavailable("Пустая запись")

    url = (getattr(settings, "speech_api_url", "") or
           "https://api.openai.com/v1/audio/transcriptions")
    model = getattr(settings, "speech_model", "") or "gpt-4o-mini-transcribe"
    language = getattr(settings, "speech_language", "") or "ru"

    # Имя, под которым отправляем, собираем сами: пришедшее от мессенджера
    # описывает его привычку, а не формат записи.
    extension, mime = _format(audio)
    stem = (filename or "voice").rsplit("/", 1)[-1].rsplit(".", 1)[0] or "voice"
    send_as = f"{stem}.{extension}"

    data = {"model": model, "response_format": "json"}
    # Подсказка языка заметно поднимает точность на коротких записях: без неё
    # «два номера на завтра» распознаётся то как русский, то как казахский.
    if language:
        data["language"] = language

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.speech_api_key}"},
                data=data,
                files={"file": (send_as, audio, mime)},
            )
            if response.status_code >= 400:
                # Тело ошибки в лог, но без ключа: этот текст видят и логи, и
                # админка.
                logger.warning(
                    "Распознавание отказало: HTTP %s %s",
                    response.status_code, response.text[:200],
                )
                raise SpeechUnavailable(f"Служба распознавания ответила {response.status_code}")
            payload = response.json()
    except SpeechUnavailable:
        raise
    except Exception as error:  # noqa: BLE001 — причина не влияет на действие
        logger.warning("Распознавание не отработало: %s", type(error).__name__)
        raise SpeechUnavailable(f"Служба распознавания недоступна: {error}") from error

    text = str(payload.get("text") or "").strip()
    logger.info("Голосовое расшифровано: %d символов", len(text))
    return text
