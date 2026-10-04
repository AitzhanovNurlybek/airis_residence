"""
Найти номер чата Telegram для технических тревог разработчику.

Зачем. Все тревоги бота ходили через тот же WhatsApp, который они и
сторожат. 4 октября 2026 закончился тариф Green API — и через WhatsApp не
уходило уже ничего, в том числе тревоги о том, что ничего не уходит.
Telegram от Green API не зависит.

Как настроить, один раз:
    1. В Telegram открыть @BotFather → /newbot → придумать имя → получить токен.
    2. Вписать токен в backend/.env строкой TELEGRAM_BOT_TOKEN=...
    3. Написать своему новому боту любое сообщение (например «привет»).
    4. Запустить:  ./.venv/Scripts/python.exe telegram_chat_id.py
       Скрипт найдёт ваш чат, пришлёт в него проверочное сообщение и напечатает,
       что вписать в Vercel → Settings → Environment Variables.

Токен не печатается: он секрет, по нему кто угодно пишет от имени бота.
"""

from __future__ import annotations

import io
import sys

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.config import get_settings  # noqa: E402


def main() -> int:
    get_settings.cache_clear()
    token = (get_settings().telegram_bot_token or "").strip()
    if not token:
        print("В backend/.env нет TELEGRAM_BOT_TOKEN — сначала шаги 1–2 из описания в начале файла.")
        return 1

    api = f"https://api.telegram.org/bot{token}"
    with httpx.Client(timeout=20) as client:
        me = client.get(f"{api}/getMe").json()
        if not me.get("ok"):
            print("Telegram не принял токен — проверьте, что скопирован целиком.")
            return 1
        print(f"Бот: @{me['result'].get('username')}")

        updates = client.get(f"{api}/getUpdates").json().get("result") or []
        chats: dict[int, str] = {}
        for item in updates:
            chat = (item.get("message") or item.get("edited_message") or {}).get("chat") or {}
            if chat.get("id"):
                chats[chat["id"]] = " ".join(
                    x for x in (chat.get("first_name"), chat.get("last_name"), chat.get("title")) if x)
        if not chats:
            print("Бот ещё не получил ни одного сообщения. Напишите ему что-нибудь и запустите снова.")
            return 1

        for chat_id, name in chats.items():
            client.post(f"{api}/sendMessage", json={
                "chat_id": chat_id,
                "text": "Проверка: технические тревоги бота Airis Residence будут приходить сюда.",
            })
            print(f"Чат: {name or 'без имени'} — проверочное сообщение отправлено.")

    print("\nВпишите в Vercel → Settings → Environment Variables (Production):")
    print("  TELEGRAM_BOT_TOKEN   — тот же токен, что в backend/.env")
    for chat_id in chats:
        print(f"  DEV_TELEGRAM_CHAT_ID = {chat_id}")
    print("и сделайте Redeploy последнего деплоя.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
