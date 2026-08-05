/**
 * ┌──────────────────────────────────────────────────────────────────┐
 * │  ТОЧКА ИНТЕГРАЦИИ БРОНИРОВАНИЯ И ОПЛАТЫ                          │
 * │                                                                  │
 * │  Весь сайт ходит за ссылкой брони СЮДА и больше никуда.          │
 * │  Чтобы подключить движок бронирования или платёжную страницу     │
 * │  банка, НЕ НУЖНО менять код — достаточно заполнить .env.local    │
 * │  (или переменные окружения на хостинге).                         │
 * │                                                                  │
 * │  Подробная инструкция: /docs/ИНТЕГРАЦИЯ.md                       │
 * └──────────────────────────────────────────────────────────────────┘
 */

import { defaultLocale, localePath, type Locale } from "./i18n/config";

export type BookingMode =
  /** Ссылка на внешний движок брони / платёжную страницу банка. */
  | "engine"
  /** Виджет банка/движка, встроенный скриптом на страницу /bronirovanie. */
  | "widget"
  /** Движок ещё не подключён: заявка через форму, WhatsApp и телефон. */
  | "request";

const env = {
  mode: process.env.NEXT_PUBLIC_BOOKING_MODE,
  url: process.env.NEXT_PUBLIC_BOOKING_URL,
  widgetScript: process.env.NEXT_PUBLIC_BOOKING_WIDGET_SRC,
  widgetHtml: process.env.NEXT_PUBLIC_BOOKING_WIDGET_HTML,
  /** Названия query-параметров у движка. У разных вендоров они разные. */
  paramCheckIn: process.env.NEXT_PUBLIC_BOOKING_PARAM_CHECKIN || "checkin",
  paramCheckOut: process.env.NEXT_PUBLIC_BOOKING_PARAM_CHECKOUT || "checkout",
  paramAdults: process.env.NEXT_PUBLIC_BOOKING_PARAM_ADULTS || "adults",
  paramRoom: process.env.NEXT_PUBLIC_BOOKING_PARAM_ROOM || "room",
  apiBase: process.env.NEXT_PUBLIC_API_BASE_URL || "",
};

function resolveMode(): BookingMode {
  if (env.mode === "engine" || env.mode === "widget" || env.mode === "request") {
    return env.mode;
  }
  // Автоопределение: если ссылку выдали — включаем движок.
  if (env.url) return "engine";
  if (env.widgetScript || env.widgetHtml) return "widget";
  return "request";
}

export const bookingConfig = {
  mode: resolveMode(),
  url: env.url ?? "",
  widgetScript: env.widgetScript ?? "",
  widgetHtml: env.widgetHtml ?? "",
  apiBase: env.apiBase,
} as const;

/** Движок подключён — кнопка «Забронировать» ведёт на реальную бронь. */
export const isBookingLive = bookingConfig.mode !== "request";

export type BookingQuery = {
  checkIn?: string; // YYYY-MM-DD
  checkOut?: string; // YYYY-MM-DD
  adults?: number;
  /** slug типа номера из lib/site.ts */
  room?: string;
};

/**
 * Куда ведёт кнопка «Забронировать».
 * До подключения движка — на внутреннюю страницу /bronirovanie
 * с формой заявки. После подключения — на движок/платёжку.
 */
export function getBookingHref(
  query: BookingQuery = {},
  locale: Locale = defaultLocale,
): string {
  if (bookingConfig.mode === "engine" && bookingConfig.url) {
    let url: URL;
    try {
      url = new URL(bookingConfig.url);
    } catch {
      return bookingConfig.url;
    }
    if (query.checkIn) url.searchParams.set(env.paramCheckIn, query.checkIn);
    if (query.checkOut) url.searchParams.set(env.paramCheckOut, query.checkOut);
    if (query.adults) url.searchParams.set(env.paramAdults, String(query.adults));
    if (query.room) url.searchParams.set(env.paramRoom, query.room);
    return url.toString();
  }

  const params = new URLSearchParams();
  if (query.checkIn) params.set("checkin", query.checkIn);
  if (query.checkOut) params.set("checkout", query.checkOut);
  if (query.adults) params.set("adults", String(query.adults));
  if (query.room) params.set("room", query.room);
  const qs = params.toString();
  return `${localePath(locale, "/bronirovanie")}${qs ? `?${qs}` : ""}`;
}

/** Внешняя ссылка открывается в новой вкладке, внутренняя — нет. */
export const bookingLinkTarget = bookingConfig.mode === "engine" ? "_blank" : undefined;

/* ------------------------------------------------------------------ */
/*  Отправка заявки на бэкенд                                          */
/* ------------------------------------------------------------------ */

export type LeadPayload = {
  name: string;
  phone: string;
  email?: string;
  checkIn?: string;
  checkOut?: string;
  adults?: number;
  room?: string;
  comment?: string;
  /** honeypot — заполняется только ботами */
  company?: string;
};

export async function submitLead(payload: LeadPayload): Promise<{ ok: boolean; error?: string }> {
  const endpoint = bookingConfig.apiBase
    ? `${bookingConfig.apiBase.replace(/\/$/, "")}/api/leads`
    : "/api/leads";

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return { ok: false, error: text || `HTTP ${res.status}` };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "network error" };
  }
}

/** Запасной канал, если бэкенд недоступен: готовый текст в WhatsApp. */
export function whatsappFallbackUrl(payload: LeadPayload, waNumber: string) {
  const lines = [
    "Здравствуйте! Хочу забронировать номер в Airis Residence.",
    payload.room ? `Тип номера: ${payload.room}` : "",
    payload.checkIn ? `Заезд: ${payload.checkIn}` : "",
    payload.checkOut ? `Выезд: ${payload.checkOut}` : "",
    payload.adults ? `Гостей: ${payload.adults}` : "",
    payload.name ? `Имя: ${payload.name}` : "",
    payload.phone ? `Телефон: ${payload.phone}` : "",
    payload.comment ? `Комментарий: ${payload.comment}` : "",
  ].filter(Boolean);
  return `${waNumber}?text=${encodeURIComponent(lines.join("\n"))}`;
}
