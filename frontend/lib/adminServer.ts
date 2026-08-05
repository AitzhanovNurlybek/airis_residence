import { cookies } from "next/headers";

/**
 * Серверная часть админки.
 *
 * Токен хранится в httpOnly-куке: браузерный JavaScript до него не
 * дотягивается, поэтому украсть сессию через XSS нельзя. Все запросы
 * админки идут через прокси /api/admin/* — он и подставляет токен.
 */

export const ADMIN_COOKIE = "airis_admin";

export const BACKEND = (process.env.BACKEND_URL || "").replace(/\/$/, "");

export async function getAdminToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(ADMIN_COOKIE)?.value ?? null;
}

/** Запрос к бэкенду от имени администратора (для серверных компонентов). */
export async function adminFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!BACKEND) {
    throw new Error("BACKEND_URL не задан — админка не может работать без бэкенда");
  }
  const token = await getAdminToken();
  return fetch(`${BACKEND}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",
  });
}

/** Проверка, что сессия ещё жива. Используется в лейауте админки. */
export async function isAdminSignedIn(): Promise<boolean> {
  if (!BACKEND) return false;
  try {
    const res = await adminFetch("/api/admin/me");
    return res.ok;
  } catch {
    return false;
  }
}
