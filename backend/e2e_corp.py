# -*- coding: utf-8 -*-
"""
Сквозная проверка корпоративного кабинета.

Работает на отдельной временной базе (_corp_e2e.db) и на подменённых доступах:
локальную базу и боевую не трогает, .env не читается для того, что подменено.

Запуск из backend/:
    .venv/Scripts/python.exe e2e_corp.py     (Windows)
    .venv/bin/python e2e_corp.py             (Linux/macOS)

Проверяется весь путь: отель заводит компанию и сотрудников, ставит корпоративные
цены; сотрудник входит, видит свои цены, оформляет и отменяет бронь; менеджер
ведёт её по статусам. Отдельно — то, что чужого не видно и внутрь не пускают.
"""
import asyncio
import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

TEST_DB = pathlib.Path("./_corp_e2e.db").resolve()
if TEST_DB.exists():
    TEST_DB.unlink()

# Переменные окружения важнее .env — подменяем базу и доступы до импорта app.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "e2e-admin-password"
os.environ["SECRET_KEY"] = "e2e-secret-key-long-enough-for-hmac-signing"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

import httpx  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app, seed_rooms_if_empty  # noqa: E402

OK, FAIL = "  ✅", "  ❌"
problems: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"{OK if condition else FAIL} {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        problems.append(label)


async def main() -> None:
    await init_db()
    await seed_rooms_if_empty()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        print("\n── Админ отеля заводит компанию ──")
        r = await c.post(
            "/api/auth/login",
            json={"username": "admin", "password": "e2e-admin-password"},
        )
        check("вход администратора отеля", r.status_code == 200, str(r.status_code))
        admin_h = {"Authorization": f"Bearer {r.json()['token']}"}

        r = await c.post(
            "/api/admin/corp/companies",
            headers=admin_h,
            json={
                "slug": "company-a",
                "name": "ТОО «Компания-пример А»",
                "bin": "000000000001",
                "contractNumber": "№001",
                "contractDate": "2026-01-15",
                "paymentTerms": "постоплата, 30 дн. (после услуг)",
                "managerName": "Отдел бронирования Airis",
                "managerEmail": "airisresidence-kz@gmail.com",
                "managerPhone": "+7 (700) 000 0001",
                "discountPercent": 12,
            },
        )
        check("создание компании", r.status_code == 201, str(r.status_code))

        r = await c.post(
            "/api/admin/corp/companies",
            headers=admin_h,
            json={"slug": "company-a", "name": "Дубль"},
        )
        check("повторный код компании отклонён", r.status_code == 409, str(r.status_code))

        print("\n── Сотрудники ──")
        r = await c.post(
            "/api/admin/corp/companies/company-a/users",
            headers=admin_h,
            json={
                "email": "Admin@Company-A.example",
                "fullName": "Айгуль Ответственная",
                "role": "admin",
                "password": "corp-pass-12345",
            },
        )
        check("создан ответственный", r.status_code == 201, str(r.status_code))
        check("почта приведена к нижнему регистру",
              r.json()["email"] == "admin@company-a.example", r.json()["email"])

        r = await c.post(
            "/api/admin/corp/companies/company-a/users",
            headers=admin_h,
            json={
                "email": "user@company-a.example",
                "fullName": "Ержан Сотрудник",
                "role": "employee",
                "password": "corp-pass-67890",
            },
        )
        check("создан сотрудник", r.status_code == 201, str(r.status_code))

        r = await c.post(
            "/api/admin/corp/companies/company-a/users",
            headers=admin_h,
            json={"email": "nopass@company-a.example", "role": "employee"},
        )
        no_pass_id = r.json()["id"]
        check("сотрудник без пароля заведён", r.status_code == 201)
        check("у него признак hasPassword=false", r.json()["hasPassword"] is False)

        r = await c.post(
            "/api/corp/login",
            json={"email": "nopass@company-a.example", "password": ""},
        )
        check("без пароля войти нельзя", r.status_code in (401, 422), str(r.status_code))

        print("\n── Корпоративные цены ──")
        r = await c.get("/api/admin/corp/companies/company-a/rates", headers=admin_h)
        check("прайс компании пуст на старте", r.json() == [], str(r.json()))

        r = await c.put(
            "/api/admin/corp/companies/company-a/rates",
            headers=admin_h,
            json=[{"roomSlug": "standart-single", "price": 26500}],
        )
        check("точечная цена сохранена", r.status_code == 200, str(r.status_code))

        r = await c.put(
            "/api/admin/corp/companies/company-a/rates",
            headers=admin_h,
            json=[{"roomSlug": "нет-такого", "price": 1}],
        )
        check("цена на несуществующий номер отклонена", r.status_code == 400, str(r.status_code))

        print("\n── Вход в кабинет ──")
        r = await c.post(
            "/api/corp/login",
            json={"email": "admin@company-a.example", "password": "неверный"},
        )
        check("неверный пароль не пускает", r.status_code == 401, str(r.status_code))

        r = await c.post(
            "/api/corp/login",
            json={"email": "admin@company-a.example", "password": "corp-pass-12345"},
        )
        check("вход ответственного", r.status_code == 200, str(r.status_code))
        boss_h = {"Authorization": f"Bearer {r.json()['token']}"}

        r = await c.post(
            "/api/corp/login",
            json={"email": "user@company-a.example", "password": "corp-pass-67890"},
        )
        staff_h = {"Authorization": f"Bearer {r.json()['token']}"}
        check("вход рядового сотрудника", r.status_code == 200, str(r.status_code))

        r = await c.get("/api/corp/me", headers={"Authorization": "Bearer not-a-real-token"})
        check("битый токен не проходит", r.status_code == 401, str(r.status_code))

        r = await c.get("/api/admin/corp/companies", headers=boss_h)
        check("корп-токен не пускает в админку отеля", r.status_code == 401, str(r.status_code))

        print("\n── Кабинет ──")
        r = await c.get("/api/corp/me", headers=boss_h)
        me = r.json()
        check("карточка компании отдаётся", me["company"]["name"].startswith("ТОО"), me["company"]["name"])
        check("условия оплаты на месте", me["company"]["paymentTerms"].startswith("постоплата"))
        check("счётчик активных броней = 0", me["activeBookings"] == 0, str(me["activeBookings"]))

        r = await c.get("/api/corp/rooms", headers=boss_h)
        rooms = {x["slug"]: x for x in r.json()}
        single = rooms["standart-single"]
        check("точечная цена важнее скидки",
              single["corpPrice"] == 26500, f"{single['publicPrice']} → {single['corpPrice']}")
        other = rooms["standart"]
        expected = other["publicPrice"] * 88 // 100 // 100 * 100
        check("скидка 12 % применена и округлена до сотни",
              other["corpPrice"] == expected, f"{other['publicPrice']} → {other['corpPrice']}")
        check("корп-цена ниже публичной", other["corpPrice"] < other["publicPrice"])

        print("\n── Бронирование ──")
        r = await c.post(
            "/api/corp/bookings",
            headers=staff_h,
            json={
                "checkIn": "2026-09-04",
                "checkOut": "2026-09-07",
                "adults": 2,
                "guestName": "Ержан Сотрудник",
                "items": [{"roomSlug": "comfort", "roomsCount": 1}],
            },
        )
        check("бронь создана", r.status_code == 201, str(r.status_code))
        booking = r.json()
        comfort = rooms["comfort"]
        check("номер брони человекочитаемый", booking["number"].startswith("K-"), booking["number"])
        check("ночей посчитано верно", booking["nights"] == 3, str(booking["nights"]))
        check("сумма = цена × ночи",
              booking["totalAmount"] == comfort["corpPrice"] * 3,
              f"{booking['totalAmount']} vs {comfort['corpPrice'] * 3}")
        check("цена в строке зафиксирована снимком",
              booking["items"][0]["pricePerNight"] == comfort["corpPrice"])
        check("статус — заявка", booking["status"] == "new", booking["status"])
        check("видно, кто оформил", booking["createdByName"] == "Ержан Сотрудник", booking["createdByName"])

        r = await c.post(
            "/api/corp/bookings",
            headers=staff_h,
            json={
                "checkIn": "2026-09-10",
                "checkOut": "2026-09-09",
                "adults": 1,
                "items": [{"roomSlug": "comfort", "roomsCount": 1}],
            },
        )
        check("выезд раньше заезда отклонён", r.status_code == 422, str(r.status_code))

        r = await c.post(
            "/api/corp/bookings",
            headers=staff_h,
            json={
                "checkIn": "2020-01-01",
                "checkOut": "2020-01-03",
                "adults": 1,
                "items": [{"roomSlug": "comfort", "roomsCount": 1}],
            },
        )
        check("прошедшая дата отклонена", r.status_code == 400, str(r.status_code))

        r = await c.post(
            "/api/corp/bookings",
            headers=staff_h,
            json={
                "checkIn": "2026-09-04",
                "checkOut": "2026-09-05",
                "adults": 5,
                "items": [{"roomSlug": "standart-single", "roomsCount": 1}],
            },
        )
        check("перебор гостей отклонён", r.status_code == 400, r.text[:80])

        print("\n── Кто что видит ──")
        r = await c.get("/api/corp/bookings", headers=boss_h)
        check("ответственный видит бронь сотрудника", len(r.json()) == 1, str(len(r.json())))

        r = await c.post(
            "/api/corp/bookings",
            headers=boss_h,
            json={
                "checkIn": "2026-09-15",
                "checkOut": "2026-09-17",
                "adults": 1,
                "items": [{"roomSlug": "standart", "roomsCount": 1}],
            },
        )
        boss_booking_id = r.json()["id"]

        r = await c.get("/api/corp/bookings", headers=staff_h)
        check("сотрудник видит только свои брони", len(r.json()) == 1, str(len(r.json())))

        r = await c.post(
            f"/api/corp/bookings/{boss_booking_id}/cancel", headers=staff_h, json={}
        )
        check("чужую бронь отменить нельзя", r.status_code == 403, str(r.status_code))

        r = await c.get("/api/corp/me", headers=boss_h)
        check("счётчик активных броней вырос до 2",
              r.json()["activeBookings"] == 2, str(r.json()["activeBookings"]))

        print("\n── Отмена и статусы ──")
        r = await c.post(
            f"/api/corp/bookings/{booking['id']}/cancel",
            headers=staff_h,
            json={"reason": "поездка отменилась"},
        )
        check("свою бронь отменить можно", r.status_code == 200, str(r.status_code))
        check("причина сохранена", r.json()["cancelReason"] == "поездка отменилась")

        r = await c.post(
            f"/api/corp/bookings/{booking['id']}/cancel", headers=staff_h, json={}
        )
        check("повторная отмена отклонена", r.status_code == 409, str(r.status_code))

        r = await c.patch(
            f"/api/admin/corp/bookings/{boss_booking_id}/status",
            headers=admin_h,
            json={"status": "invoiced", "invoiceNumber": "СЧ-2026-014"},
        )
        check("менеджер выставил счёт", r.status_code == 200 and r.json()["invoiceNumber"] == "СЧ-2026-014")

        r = await c.patch(
            f"/api/admin/corp/bookings/{boss_booking_id}/status",
            headers=admin_h,
            json={"status": "paid"},
        )
        r = await c.get("/api/corp/me", headers=boss_h)
        check("оплаченное ушло из активных",
              r.json()["activeBookings"] == 0, str(r.json()["activeBookings"]))
        check("сумма оплаченного посчиталась",
              r.json()["paidAmount"] > 0, str(r.json()["paidAmount"]))

        print("\n── Смена пароля и отключение доступа ──")
        r = await c.post(
            "/api/corp/password",
            headers=staff_h,
            json={"current_password": "неверный", "new_password": "новый-пароль-123"},
        )
        check("неверный текущий пароль не принят", r.status_code == 400, str(r.status_code))

        r = await c.post(
            "/api/corp/password",
            headers=staff_h,
            json={"current_password": "corp-pass-67890", "new_password": "новый-пароль-123"},
        )
        check("пароль сменён", r.status_code == 204, str(r.status_code))

        r = await c.post(
            "/api/corp/login",
            json={"email": "user@company-a.example", "password": "новый-пароль-123"},
        )
        check("вход с новым паролем", r.status_code == 200, str(r.status_code))

        r = await c.patch(
            f"/api/corp/employees/{no_pass_id}", headers=staff_h, json={"role": "admin"}
        )
        check("рядовой сотрудник не управляет коллегами", r.status_code == 403, str(r.status_code))

        r = await c.patch(
            "/api/corp/employees/999999", headers=boss_h, json={"isActive": False}
        )
        check("чужой сотрудник не находится", r.status_code == 404, str(r.status_code))

        r = await c.patch(
            f"/api/corp/employees/{no_pass_id}", headers=boss_h, json={"isActive": False}
        )
        check("ответственный отключил сотрудника", r.status_code == 200, str(r.status_code))

        print("\n── Изоляция компаний ──")
        # Заводим вторую компанию: главный вопрос безопасности здесь не «пустят
        # ли чужого», а «увидит ли клиент А данные клиента Б».
        r = await c.post(
            "/api/admin/corp/companies",
            headers=admin_h,
            json={"slug": "company-b", "name": "ТОО «Компания-пример Б»", "discountPercent": 30},
        )
        check("вторая компания создана", r.status_code == 201, str(r.status_code))

        r = await c.post(
            "/api/admin/corp/companies/company-b/users",
            headers=admin_h,
            json={
                "email": "boss@company-b.example",
                "fullName": "Борис Второй",
                "role": "admin",
                "password": "bee-pass-12345",
            },
        )
        check("сотрудник второй компании заведён", r.status_code == 201, str(r.status_code))

        r = await c.post(
            "/api/corp/login",
            json={"email": "boss@company-b.example", "password": "bee-pass-12345"},
        )
        check("вход во вторую компанию", r.status_code == 200, str(r.status_code))
        bee_h = {"Authorization": f"Bearer {r.json()['token']}"}

        r = await c.get("/api/corp/bookings", headers=bee_h)
        check("чужих броней не видно", r.json() == [], f"вернулось {len(r.json())}")

        # Прямой заход по id чужой брони — то, что попробует любопытный
        # сотрудник, подставив число в адрес.
        r = await c.post(
            f"/api/corp/bookings/{boss_booking_id}/cancel", headers=bee_h, json={}
        )
        check("чужую бронь не отменить по id", r.status_code == 404, str(r.status_code))

        r = await c.get("/api/corp/me", headers=bee_h)
        check(
            "видит только свою компанию",
            "Б" in r.json()["company"]["name"],
            r.json()["company"]["name"],
        )

        r = await c.get("/api/corp/rooms", headers=bee_h)
        bee_rooms = {x["slug"]: x for x in r.json()}
        # У Б скидка 30 %, у А точечная цена 26 500 на standart-single.
        check(
            "цены второй компании свои, а не первой",
            bee_rooms["standart-single"]["corpPrice"] != 26500,
            str(bee_rooms["standart-single"]["corpPrice"]),
        )

        r = await c.get("/api/corp/employees", headers=bee_h)
        emails = [u["email"] for u in r.json()]
        check(
            "в списке сотрудников только свои",
            all("company-b" in e for e in emails),
            ", ".join(emails),
        )

        print("\n── Защита от перебора ──")
        # Одиннадцатая попытка по одной почте должна упереться в предел.
        codes = []
        for _ in range(12):
            rr = await c.post(
                "/api/corp/login",
                json={"email": "boss@company-b.example", "password": "не-тот-пароль"},
            )
            codes.append(rr.status_code)
        check("перебор одной учётки останавливается", 429 in codes, f"коды: {sorted(set(codes))}")
        check(
            "до предела отвечало 401, а не 429 сразу",
            codes[0] == 401,
            str(codes[0]),
        )

        # Другая почта из того же теста не должна пострадать: предел по учётке,
        # а не общий на всех.
        r = await c.post(
            "/api/corp/login",
            json={"email": "admin@company-a.example", "password": "corp-pass-12345"},
        )
        check(
            "другая учётка не заблокирована заодно",
            r.status_code == 200,
            str(r.status_code),
        )

        r = await c.patch(
            f"/api/admin/corp/companies/company-a", headers=admin_h, json={"isActive": False}
        )
        r = await c.get("/api/corp/me", headers=boss_h)
        check("при остановке договора кабинет закрывается",
              r.status_code == 403, str(r.status_code))

    print()
    if problems:
        print(f"❌ Провалено проверок: {len(problems)}")
        for p in problems:
            print("   -", p)
        sys.exit(1)
    print("✅ Все проверки прошли")


asyncio.run(main())
