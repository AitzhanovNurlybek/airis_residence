"""
Проверка после переноса бота на другой номер.

Перепривязка Green API — это выход из аккаунта и вход другим номером.
Настройки инстанса при этом должны уцелеть, но «должны» здесь недостаточно:
если сбросился адрес вебхука, гости пишут в пустоту, и узнаётся это по
жалобе через сутки.

Скрипт отвечает на четыре вопроса: какой номер привязан, цел ли адрес
вебхука, не осталось ли настроек, которые мешают отвечать быстро, и
проходит ли сообщение весь путь от вебхука до ответа.

Запуск:
    ./.venv/Scripts/python.exe proverka_nomera.py

Ничего не меняет и гостям не пишет: тестовое сообщение отправляется от имени
несуществующего номера, а ответ на него никуда не уходит.
"""

from __future__ import annotations

import asyncio
import io
import sys
import time

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.config import get_settings  # noqa: E402

#: Куда Green API обязан стучаться. Совпадение проверяется по началу строки:
#: ключ в адресе у каждого свой, и сравнивать его незачем.
EXPECTED_WEBHOOK = "https://airisresidence.kz/api/backend/api/webhooks/whatsapp"

#: Номер, от имени которого идёт проверка. Несуществующий: ответ на него
#: Green API отправить не сможет, и живого человека мы не потревожим.
TEST_CHAT = "70000000000@c.us"

ok_count = 0
problems: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global ok_count
    if ok:
        ok_count += 1
        print(f"  [ок] {name}")
    else:
        problems.append(f"{name}{' — ' + detail if detail else ''}")
        print(f"  [!!] {name}" + (f" — {detail}" if detail else ""))


async def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    base = f"https://api.green-api.com/waInstance{settings.green_api_id}"

    print("\n== Номер и состояние ==")
    async with httpx.AsyncClient(timeout=60) as client:
        state = await client.get(f"{base}/getStateInstance/{settings.green_api_token}")
        status = str((state.json() or {}).get("stateInstance", ""))
        check("инстанс авторизован", status == "authorized", f"состояние «{status}»")
        if status != "authorized":
            print("\nДальше проверять нечего: сначала отсканируйте QR-код.")
            return 1

        settings_answer = await client.get(f"{base}/getSettings/{settings.green_api_token}")
        live = settings_answer.json() or {}

    wid = str(live.get("wid", ""))
    print(f"  привязан номер: +{wid.split('@')[0]}")

    print("\n== Настройки инстанса ==")
    hook = str(live.get("webhookUrl") or "")
    check("адрес вебхука на месте", hook.startswith(EXPECTED_WEBHOOK),
          f"сейчас «{hook.split('?')[0] or 'пусто'}»")
    check("ключ вебхука задан", bool(live.get("webhookUrlToken")))
    check("приём входящих включён", str(live.get("incomingWebhook")) == "yes",
          str(live.get("incomingWebhook")))
    # Автопечать добавляет к каждому ответу 6–9 секунд ожидания. Гость видит
    # «печатает…» и всё равно ждёт дольше, чем без неё.
    check("автопечать выключена", str(live.get("autoTyping", "0")) in ("0", "no", "False"),
          str(live.get("autoTyping")))
    delay = int(live.get("delaySendMessagesMilliseconds") or 0)
    check("задержка отправки минимальная", delay <= 1000, f"{delay} мс")
    check("прочитанным отмечаем при ответе",
          str(live.get("markIncomingMessagesReadedOnReply")) == "yes",
          str(live.get("markIncomingMessagesReadedOnReply")))

    print("\n== Путь сообщения целиком ==")
    secret = (settings.whatsapp_webhook_secret or "").strip()
    check("секрет вебхука задан", bool(secret))
    if secret:
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                answer = await client.post(
                    f"{EXPECTED_WEBHOOK}",
                    params={"key": secret},
                    json={
                        "typeWebhook": "incomingMessageReceived",
                        # Идентификатор свой на каждый запуск: у вебхука есть
                        # защита от повторов, и с постоянным номером вторая
                        # проверка отбрасывалась как дубль. Выглядело это как
                        # поломка бота — ровно в тот момент, когда проверку и
                        # запускают, сразу после переноса номера.
                        "idMessage": f"PROVERKA-PERENOSA-{int(time.time())}",
                        "instanceData": {"wid": wid},
                        "senderData": {"chatId": TEST_CHAT, "senderName": "Проверка"},
                        "messageData": {
                            "typeMessage": "textMessage",
                            # Текст тоже свой на каждый запуск. Поверх дедупа
                            # по идентификатору есть вторая защита — от той же
                            # фразы из того же чата за последние полторы
                            # минуты. Два прогона подряд она принимала за
                            # повтор, и проверка снова врала про поломку.
                            "textMessageData": {
                                "textMessage": f"во сколько заезд? ({int(time.time())})"
                            },
                        },
                    },
                )
                body = answer.json()
            except Exception as error:  # noqa: BLE001
                answer, body = None, {"error": str(error)}
        code = answer.status_code if answer is not None else 0
        # Отправка гостю не пройдёт — номер выдуман, — но всё, что до неё,
        # проверяется по-настоящему: разбор, история, обращение к модели.
        check("вебхук принимает сообщение", code == 200, f"HTTP {code} {str(body)[:120]}")
        check("сообщение дошло до обработки",
              bool(body.get("replied") or body.get("error") == "send failed"),
              str(body)[:120])

    print("\n== Итог ==")
    if problems:
        print(f"  прошло {ok_count}, нужно поправить {len(problems)}:")
        for item in problems:
            print(f"    · {item}")
        return 1
    print(f"  всё в порядке: {ok_count} проверок")
    print(f"  бот отвечает гостям с номера +{wid.split('@')[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
