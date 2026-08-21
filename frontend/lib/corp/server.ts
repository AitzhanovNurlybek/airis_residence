import { cookies } from "next/headers";

import { DEFAULT_LOCALE, isLocale, type Locale } from "./dictionary";
import type { CorpBooking, CorpMe, CorpRoom, CorpUser } from "./types";

/**
 * Серверная часть корпоративного кабинета.
 *
 * Устроена как админка отеля (lib/adminServer.ts) и по тем же причинам: токен
 * лежит в httpOnly-куке, браузер ходит только на свой домен, бэкенд не обязан
 * быть открыт наружу. Разница одна — своя кука, чтобы сотрудник компании и
 * администратор отеля могли сидеть в одном браузере не мешая друг другу.
 */

export const CORP_COOKIE = "airis_corp";

/**
 * Язык кабинета. Не httpOnly намеренно: это настройка интерфейса, а не секрет,
 * и переключателю удобнее иметь к ней доступ. Год жизни — чтобы человек
 * выбрал язык один раз, а не каждую сессию.
 */
export const CORP_LANG_COOKIE = "airis_corp_lang";
export const CORP_LANG_MAX_AGE = 60 * 60 * 24 * 365;

export const BACKEND = (process.env.BACKEND_URL || "").replace(/\/$/, "");

export async function getCorpToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(CORP_COOKIE)?.value ?? null;
}

export async function getCorpLocale(): Promise<Locale> {
  const store = await cookies();
  const saved = store.get(CORP_LANG_COOKIE)?.value;
  return isLocale(saved) ? saved : DEFAULT_LOCALE;
}

/** Запрос к бэкенду от имени сотрудника компании (для серверных компонентов). */
export async function corpFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!BACKEND) {
    throw new Error("BACKEND_URL не задан — корпоративный кабинет без бэкенда не работает");
  }
  const token = await getCorpToken();
  return fetch(`${BACKEND}/api/corp${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",
  });
}

/**
 * Читает данные или отдаёт null.
 *
 * Отдельная обёртка, потому что «не вошёл» и «сервер лежит» страница
 * обрабатывает одинаково — уводит на форму входа, — а вот тихо показать
 * пустой кабинет вместо ошибки нельзя: человек решит, что у него нет броней.
 */
async function readJson<T>(path: string): Promise<T | null> {
  if (!BACKEND) return null;
  try {
    const res = await corpFetch(path);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function getCorpMe(): Promise<CorpMe | null> {
  return readJson<CorpMe>("/me");
}

export function getCorpBookings(): Promise<CorpBooking[] | null> {
  return readJson<CorpBooking[]>("/bookings");
}

export function getCorpRooms(): Promise<CorpRoom[] | null> {
  return readJson<CorpRoom[]>("/rooms");
}

/** Список сотрудников. Бэкенд отдаёт его только ответственному. */
export function getCorpEmployees(): Promise<CorpUser[] | null> {
  return readJson<CorpUser[]>("/employees");
}
