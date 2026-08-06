"use client";

/**
 * Запросы админки из браузера.
 * Всё идёт на свой же домен через /api/admin/* — токен подставит прокси.
 */

export class AdminError extends Error {
  /** Код ответа. Нужен, чтобы отличать «так нельзя» от «сломалось»:
   *  например 501 у видео значит «хранилище не выдаёт временные ссылки». */
  constructor(
    message: string,
    readonly status = 0,
  ) {
    super(message);
  }
}

async function unwrap(res: Response) {
  if (res.status === 401) {
    // Сессия истекла — возвращаем на вход, чтобы не ловить череду ошибок.
    if (typeof window !== "undefined") window.location.href = "/admin/login";
    throw new AdminError("Сессия истекла, войдите заново");
  }
  if (res.status === 204) return null;

  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail =
      (data as { detail?: string; error?: string })?.detail ??
      (data as { error?: string })?.error ??
      `Ошибка ${res.status}`;
    throw new AdminError(
      typeof detail === "string" ? detail : "Не удалось сохранить",
      res.status,
    );
  }
  return data;
}

export async function adminGet<T>(path: string): Promise<T> {
  return (await unwrap(await fetch(`/api/admin${path}`, { cache: "no-store" }))) as T;
}

export async function adminSend<T>(
  path: string,
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  body?: unknown,
): Promise<T> {
  const res = await fetch(`/api/admin${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return (await unwrap(res)) as T;
}

/** Загрузка файлов. Content-Type проставит браузер — руками его трогать нельзя. */
export async function adminUpload<T>(path: string, files: File[]): Promise<T> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const res = await fetch(`/api/admin${path}`, { method: "POST", body: form });
  return (await unwrap(res)) as T;
}

export async function adminLogout() {
  await fetch("/api/admin/login", { method: "DELETE" });
  window.location.href = "/admin/login";
}
