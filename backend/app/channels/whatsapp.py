"""
WhatsApp через Green API.

Канал делает две вещи: приносит входящее сообщение и уносит ответ. Всё, что
консьерж говорит и чего не говорит, живёт в `concierge.py` и от канала не
зависит — иначе добавление Instagram размножило бы правила по копиям.

Приём устроен опросом очереди (`receiveNotification`), а не вебхуком. Значит
не нужен публичный адрес: бот работает с любой машины, в том числе с ноутбука
при отладке. Клиент здесь свой, но повторяет проверенный в соседнем проекте
владельца (`almaty-leads-agent/src/outreach/green_api.py`) — вместе с граблями,
которые там уже собраны.

Грабли, ради которых стоит читать код целиком:

* подтверждение приёма (`deleteNotification`) может не пройти, и тогда то же
  сообщение придёт снова. Дедуп обязателен, и он не здесь, а в `dialogs.py`;
* между отправками нужна пауза, иначе номер блокируют. Особенно первую неделю
  нового номера;
* в очередь падают и наши собственные исходящие, и статусы доставки. Отвечать
  на них нельзя — получится разговор с самим собой.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.green-api.com/waInstance{id}/{method}/{token}"

#: Типы уведомлений, на которые отвечаем. Всё остальное — исходящие, статусы
#: доставки, изменения в группах — пропускаем.
INCOMING = {"incomingMessageReceived"}

#: Типы, на которые молчим сознательно: это не обращения к отелю.
IGNORED_KINDS = {
    "reactionMessage",       # «палец вверх» на нашу реплику
    "pollMessage",
    "pollUpdateMessage",
    "editedMessage",
    "deletedMessage",
    "groupInviteMessage",
}


class WhatsAppError(RuntimeError):
    pass


@dataclass(frozen=True)
class Incoming:
    """Входящее сообщение, приведённое к общему виду."""

    message_id: str
    chat_id: str
    phone: str
    sender_name: str
    text: str
    #: Ссылка на присланный файл и его имя, если это не текст.
    file_url: str = ""
    file_name: str = ""
    #: Голосовое сообщение. Отличается от обычного файла: разбирать его как
    #: платёжку бессмысленно, а молчать в ответ нельзя.
    is_voice: bool = False
    #: Как назвал сообщение мессенджер. Нужен снаружи ровно для одного
    #: решения: если прочитать содержимое не вышло, промолчать или ответить.
    kind: str = ""

    @property
    def is_group(self) -> bool:
        return self.chat_id.endswith("@g.us")

    @property
    def has_file(self) -> bool:
        return bool(self.file_url)

    @property
    def readable(self) -> bool:
        """Есть ли что обрабатывать."""
        return bool(self.text or self.file_url or self.is_voice)

    @property
    def is_noise(self) -> bool:
        """Сообщение, на которое отвечать не надо.

        Реакция «палец вверх» на реплику консьержа — не вопрос, и ответ на
        неё выглядит навязчивостью. То же с опросами и служебными событиями
        вроде правки или удаления сообщения.

        Список нарочно короткий и закрытый: всё, чего в нём нет и что не
        удалось прочитать, получает ответ. Молчание должно быть решением, а
        не следствием незнакомого типа — именно так уже терялись голосовые и
        ответы с цитатой.
        """
        return self.kind in IGNORED_KINDS


class WhatsAppChannel:
    """Приём и отправка сообщений WhatsApp."""

    name = "whatsapp"

    def __init__(self, id_instance: str, token: str, timeout: float = 30.0) -> None:
        if not id_instance or not token:
            raise WhatsAppError(
                "Нужны GREEN_API_ID и GREEN_API_TOKEN в backend/.env"
            )
        self._id = id_instance.strip()
        self._token = token.strip()
        self._timeout = timeout

    def _url(self, method: str) -> str:
        return BASE_URL.format(id=self._id, method=quote(method, safe="/"), token=self._token)

    # ───────────────────────────── состояние ─────────────────────────────

    async def state(self) -> str:
        """`authorized` — номер на связи. Всё остальное значит, что бот нем."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(self._url("getStateInstance"))
            response.raise_for_status()
            return str(response.json().get("stateInstance", "unknown"))

    # ─────────────────────────────── приём ───────────────────────────────

    async def receive(self, wait_seconds: int = 20) -> tuple[int | None, Incoming | None]:
        """
        Взять сообщение из очереди.

        Возвращает пару «квитанция, сообщение». Квитанция есть всегда, когда
        что-то пришло, — её надо подтвердить даже для тех уведомлений, на
        которые мы не отвечаем, иначе очередь встанет на них навсегда.
        """
        async with httpx.AsyncClient(timeout=self._timeout + wait_seconds) as client:
            try:
                response = await client.get(
                    self._url("receiveNotification"),
                    params={"receiveTimeout": wait_seconds},
                )
                response.raise_for_status()
            except httpx.HTTPError as error:
                raise WhatsAppError(f"очередь недоступна: {error}") from error

        if not response.text or response.text.strip() in ("", "null"):
            return None, None

        payload = response.json() or {}
        receipt = payload.get("receiptId")
        body = payload.get("body") or {}
        return receipt, _parse(body)

    async def confirm(self, receipt_id: int) -> bool:
        """
        Убрать уведомление из очереди.

        Если не вышло — не беда: сообщение придёт снова, а дедуп по его
        идентификатору не даст ответить дважды. Поэтому исключение здесь не
        поднимаем, а просто сообщаем неудачу.
        """
        # _url() кладёт токен ПОСЛЕДНИМ сегментом (.../{method}/{token}), а
        # у deleteNotification после токена идёт ещё receiptId — его нельзя
        # засунуть в method вместе с остальным, иначе он окажется ПЕРЕД
        # токеном: .../deleteNotification/{receipt_id}/{token} вместо
        # верного .../deleteNotification/{token}/{receipt_id}. С таким
        # порядком Green API не находил метод и подтверждение не проходило
        # ни разу — бот вечно топтался на одном и том же уведомлении,
        # думая, что confirm() просто иногда не срабатывает.
        url = f"{self._url('deleteNotification')}/{receipt_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.delete(url)
            except httpx.HTTPError:
                return False
            return response.status_code < 400

    # ────────────────────────────── отправка ──────────────────────────────

    async def send(self, chat_id: str, text: str) -> str:
        """Отправить текст. Возвращает идентификатор сообщения."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    self._url("sendMessage"),
                    json={"chatId": chat_id, "message": for_whatsapp(text)},
                )
            except httpx.HTTPError as error:
                raise WhatsAppError(f"сеть: {error}") from error

        if response.status_code >= 400:
            raise WhatsAppError(f"HTTP {response.status_code}: {response.text[:200]}")
        message_id = (response.json() or {}).get("idMessage")
        if not message_id:
            raise WhatsAppError(f"нет idMessage в ответе: {response.text[:200]}")
        return str(message_id)

    async def send_file(self, chat_id: str, url: str, caption: str = "",
                        filename: str = "") -> str:
        """Отправить снимок по ссылке.

        Гость, попросивший «покажите фото», хочет увидеть номер, а не открыть
        браузер. Ссылка вместо изображения — это отказ, оформленный как ответ.

        Green API забирает файл по ссылке сам, поэтому картинку никуда не
        нужно выгружать: снимки уже лежат в открытом хранилище сайта.
        """
        payload = {"chatId": chat_id, "urlFile": url,
                   "fileName": filename or url.rsplit("/", 1)[-1] or "photo.jpg"}
        if caption:
            payload["caption"] = for_whatsapp(caption)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(self._url("sendFileByUrl"), json=payload)
            except httpx.HTTPError as error:
                raise WhatsAppError(f"сеть: {error}") from error

        if response.status_code >= 400:
            raise WhatsAppError(f"HTTP {response.status_code}: {response.text[:200]}")
        message_id = (response.json() or {}).get("idMessage")
        if not message_id:
            raise WhatsAppError(f"нет idMessage в ответе: {response.text[:200]}")
        return str(message_id)

    async def download(self, url: str) -> bytes:
        """Забрать присланный файл — чек или скан платёжки."""
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content


# ─────────────────────────────── разбор ───────────────────────────────


def _parse(body: dict[str, Any]) -> Incoming | None:
    if str(body.get("typeWebhook")) not in INCOMING:
        return None

    data = body.get("messageData") or {}
    sender = body.get("senderData") or {}
    chat_id = str(sender.get("chatId") or "")
    if not chat_id:
        return None

    text = ""
    file_url = ""
    file_name = ""
    is_voice = False

    kind = str(data.get("typeMessage") or "")

    # Текст ищем во всех известных местах, а не по типу сообщения.
    #
    # Разбор «по типу» уже дважды терял гостя молча. Сначала на голосовых, а
    # 2026-08-30 — на ответе с цитатой: гость нажал «ответить» на сообщение
    # бота и написал «На троих». WhatsApp прислал это типом `quotedMessage`,
    # ветки для него не было, текст остался пустым, и вебхук отчитался
    # «пустое сообщение». Гость прождал три часа.
    #
    # Список типов у мессенджера открытый и пополняется без предупреждения,
    # поэтому неизвестный тип не должен означать потерянное сообщение.
    # Смотрим в контейнеры: если текст где-то есть — он и есть сообщение.
    for holder, field in (
        ("textMessageData", "textMessage"),
        ("extendedTextMessageData", "text"),
        ("fileMessageData", "caption"),
    ):
        found = (data.get(holder) or {}).get(field)
        if found:
            text = str(found)
            break

    payload = data.get("fileMessageData") or {}
    if payload.get("downloadUrl"):
        file_url = str(payload.get("downloadUrl") or "")
        file_name = str(payload.get("fileName") or "")

    # Голосовое: по типу либо по содержимому. Расшифровка включается ключом;
    # без неё гость получает просьбу написать текстом. Молчать нельзя ни при
    # каком раскладе — человек решит, что отель его игнорирует.
    mime = str(payload.get("mimeType") or "")
    if kind in ("audioMessage", "pttMessage", "voiceMessage") or mime.startswith("audio/"):
        is_voice = True
        if not file_name:
            file_name = "voice.oga"

    return Incoming(
        message_id=str(body.get("idMessage") or ""),
        chat_id=chat_id,
        phone=_phone(chat_id),
        sender_name=str(sender.get("senderName") or ""),
        text=text.strip(),
        file_url=file_url,
        file_name=file_name,
        is_voice=is_voice,
        kind=kind,
    )


def _phone(chat_id: str) -> str:
    """`77015550011@c.us` → `+77015550011`."""
    digits = re.sub(r"\D", "", chat_id.split("@")[0])
    return f"+{digits}" if digits else ""


#: Заголовки и списки, которые WhatsApp не умеет. Оставленные как есть, они
#: приезжают гостю решётками и звёздочками — сразу видно машину.
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BULLET = re.compile(r"^\s{0,3}[-*]\s+", re.MULTILINE)


def for_whatsapp(text: str) -> str:
    """
    Причесать ответ под мессенджер.

    Модель иногда сползает в разметку: заголовки решётками, жирный двумя
    звёздочками, списки дефисами. В WhatsApp жирный — одна звёздочка, а
    заголовков нет вовсе, и гость получает текст с мусором.
    """
    out = _HEADING.sub("", text)
    out = _BOLD.sub(r"*\1*", out)
    out = _BULLET.sub("• ", out)
    # Три и больше пустых строк подряд в мессенджере выглядят обрывом связи.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
