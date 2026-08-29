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
                files={"file": (filename, audio, "application/octet-stream")},
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
