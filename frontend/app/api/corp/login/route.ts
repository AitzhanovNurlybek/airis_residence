import { NextResponse } from "next/server";

import { BACKEND, CORP_COOKIE } from "@/lib/corp/server";

export const runtime = "nodejs";

/** Вход в кабинет: меняем почту и пароль на токен, кладём его в httpOnly-куку. */
export async function POST(request: Request) {
  if (!BACKEND) {
    return NextResponse.json(
      { error: "BACKEND_URL не задан. Кабинет работает только вместе с бэкендом." },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password) {
    return NextResponse.json({ error: "Введите почту и пароль" }, { status: 400 });
  }

  const res = await fetch(`${BACKEND}/api/corp/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: body.email, password: body.password }),
    cache: "no-store",
  }).catch(() => null);

  if (!res) {
    return NextResponse.json({ error: "Сервер недоступен" }, { status: 502 });
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json(
      { error: data?.detail ?? "Неверная почта или пароль" },
      { status: res.status },
    );
  }

  // secure по фактическому протоколу, а не по режиму сборки: иначе прод-сборка,
  // запущенная локально по http, не сможет войти. На этом уже спотыкались
  // в админке, повторять не будем.
  const isHttps =
    request.headers.get("x-forwarded-proto") === "https" ||
    new URL(request.url).protocol === "https:";

  const response = NextResponse.json({
    ok: true,
    role: data.role,
    companyName: data.company_name,
  });
  response.cookies.set({
    name: CORP_COOKIE,
    value: data.token,
    httpOnly: true,
    sameSite: "lax",
    secure: isHttps,
    path: "/",
    expires: new Date(data.expires_at * 1000),
  });
  return response;
}

/** Выход: гасим куку. */
export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({ name: CORP_COOKIE, value: "", path: "/", maxAge: 0 });
  return response;
}
