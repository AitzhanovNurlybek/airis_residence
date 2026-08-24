"""
Каналы: откуда приходит сообщение и куда уходит ответ.

Канал не знает, что отвечать, — он приносит текст и уносит готовое. Правила
разговора живут в `concierge.py` и одинаковы везде: иначе WhatsApp и Instagram
разошлись бы в поведении, и чинить пришлось бы дважды.

Что должен уметь канал: получить входящее, подтвердить приём, отправить ответ,
скачать присланный файл. Всё.
"""

from .whatsapp import Incoming, WhatsAppChannel, WhatsAppError, for_whatsapp

__all__ = ["Incoming", "WhatsAppChannel", "WhatsAppError", "for_whatsapp"]
