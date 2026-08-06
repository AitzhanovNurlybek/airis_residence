import { NextResponse } from "next/server";
import { rooms, site } from "@/lib/site";

/**
 * Приём заявок на бронирование.
 *
 * Работает в двух режимах:
 *  1. Самостоятельно — шлёт заявку в Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID).
 *     Этого хватает, если сайт живёт на Vercel без отдельного бэкенда.
 *  2. Прокси — если задан BACKEND_URL, пересылает заявку в FastAPI,
 *     где она пишется в базу и попадает в админку.
 *
 * Хранить токены только в переменных окружения. В коде их быть не должно.
 */

export const runtime = "nodejs";

const TELEGRAM_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const BACKEND_URL = process.env.BACKEND_URL;

/** Примитивный лимит: не больше 5 заявок с одного IP за 10 минут. */
const WINDOW_MS = 10 * 60 * 1000;
const MAX_PER_WINDOW = 5;
const hits = new Map<string, number[]>();

function rateLimited(ip: string) {
  const now = Date.now();
  const recent = (hits.get(ip) ?? []).filter((t) => now - t < WINDOW_MS);
  recent.push(now);
  hits.set(ip, recent);
  if (hits.size > 5000) hits.clear();
  return recent.length > MAX_PER_WINDOW;
}

type Lead = {
  name?: string;
  phone?: string;
  email?: string;
  checkIn?: string;
  checkOut?: string;
  adults?: number;
  room?: string;
  comment?: string;
  company?: string;
};

const clean = (v: unknown, max = 400) =>
  typeof v === "string" ? v.trim().slice(0, max) : "";

export async function POST(request: Request) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    request.headers.get("x-real-ip") ??
    "unknown";

  if (rateLimited(ip)) {
    return NextResponse.json({ error: "Слишком много заявок. Позвоните нам." }, { status: 429 });
  }

  let body: Lead;
  try {
    body = (await request.json()) as Lead;
  } catch {
    return NextResponse.json({ error: "Некорректный запрос" }, { status: 400 });
  }

  // honeypot: поле скрыто от людей, заполняют только боты
  if (clean(body.company)) {
    return NextResponse.json({ ok: true });
  }

  // Гостей может не быть в форме. Ноль бэкенд не принимает (минимум 1),
  // поэтому неизвестное значение не отправляем вовсе — там свой умолчание.
  const adults = Number(body.adults);
  const lead = {
    name: clean(body.name, 120),
    phone: clean(body.phone, 40),
    email: clean(body.email, 160),
    checkIn: clean(body.checkIn, 20),
    checkOut: clean(body.checkOut, 20),
    adults: Number.isFinite(adults) && adults >= 1 ? Math.min(adults, 10) : undefined,
    room: clean(body.room, 60),
    comment: clean(body.comment, 1000),
  };

  if (!lead.name || lead.phone.replace(/\D/g, "").length < 10) {
    return NextResponse.json({ error: "Укажите имя и корректный телефон" }, { status: 422 });
  }

  const roomName = rooms.find((r) => r.slug === lead.room)?.shortName ?? "не выбран";

  // Заявка считается принятой, только если её кто-то реально забрал.
  let delivered = false;

  // 1. Пересылаем в собственный бэкенд, если он поднят
  if (BACKEND_URL) {
    try {
      const res = await fetch(`${BACKEND_URL.replace(/\/$/, "")}/api/leads`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(process.env.BACKEND_API_KEY ? { "X-API-Key": process.env.BACKEND_API_KEY } : {}),
        },
        body: JSON.stringify(lead),
      });
      if (res.ok) delivered = true;
      else console.error("backend lead failed", res.status, await res.text());
    } catch (e) {
      console.error("backend lead error", e);
    }
  }

  // 2. Дублируем в Telegram — заявку видно сразу, без захода в админку
  if (TELEGRAM_TOKEN && TELEGRAM_CHAT_ID) {
    const text = [
      "🏨 *Новая заявка с сайта*",
      "",
      `👤 ${lead.name}`,
      `📞 ${lead.phone}`,
      lead.email ? `✉️ ${lead.email}` : "",
      "",
      `🛏 Номер: ${roomName}`,
      `📅 ${lead.checkIn || "—"} → ${lead.checkOut || "—"}`,
      `👥 Гостей: ${lead.adults || "—"}`,
      lead.comment ? `\n💬 ${lead.comment}` : "",
    ]
      .filter(Boolean)
      .join("\n");

    try {
      const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: TELEGRAM_CHAT_ID,
          text,
          parse_mode: "Markdown",
          disable_web_page_preview: true,
        }),
      });
      if (res.ok) delivered = true;
      else console.error("telegram failed", res.status, await res.text());
    } catch (e) {
      console.error("telegram error", e);
    }
  }

  // Заявку не забрал никто: каналы не настроены либо оба отказали.
  // Молчать нельзя — гость уйдёт уверенным, что его ждут.
  if (!delivered) {
    console.error("Заявка никуда не доставлена:", lead);
    return NextResponse.json(
      {
        error: `Не удалось отправить заявку. Позвоните ${site.contacts.phonePrimary}.`,
      },
      { status: 503 },
    );
  }

  return NextResponse.json({ ok: true });
}
