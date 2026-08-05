import { NextResponse } from "next/server";
import { ADMIN_COOKIE, BACKEND } from "@/lib/adminServer";

export const runtime = "nodejs";

/** Вход: меняем логин и пароль на токен, кладём его в httpOnly-куку. */
export async function POST(request: Request) {
  if (!BACKEND) {
    return NextResponse.json(
      { error: "BACKEND_URL не задан. Админка работает только вместе с бэкендом." },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => null);
  if (!body?.username || !body?.password) {
    return NextResponse.json({ error: "Введите логин и пароль" }, { status: 400 });
  }

  const res = await fetch(`${BACKEND}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: body.username, password: body.password }),
    cache: "no-store",
  }).catch(() => null);

  if (!res) {
    return NextResponse.json({ error: "Сервер недоступен" }, { status: 502 });
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json(
      { error: data?.detail ?? "Неверный логин или пароль" },
      { status: res.status },
    );
  }

  // secure ставим по фактическому протоколу, а не по режиму сборки:
  // иначе прод-сборка, запущенная локально по http, не сможет войти.
  const isHttps =
    request.headers.get("x-forwarded-proto") === "https" ||
    new URL(request.url).protocol === "https:";

  const response = NextResponse.json({ ok: true, username: data.username });
  response.cookies.set({
    name: ADMIN_COOKIE,
    value: data.token,
    httpOnly: true,
    sameSite: "lax",
    secure: isHttps,
    path: "/",
    expires: new Date(data.expiresAt * 1000),
  });
  return response;
}

/** Выход: просто гасим куку. */
export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({ name: ADMIN_COOKIE, value: "", path: "/", maxAge: 0 });
  return response;
}
