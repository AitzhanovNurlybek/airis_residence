import { NextResponse } from "next/server";

import { BACKEND, CORP_COOKIE } from "@/lib/corp/server";

export const runtime = "nodejs";

/**
 * Прокси между кабинетом в браузере и FastAPI.
 *
 * То же, что у админки отеля: токен в httpOnly-куке недоступен странице,
 * браузер ходит на свой домен (значит нет CORS), а бэкенд не обязан быть
 * открыт наружу.
 *
 * Кэш здесь не гасим, в отличие от админского прокси: корпоративные данные
 * нигде не кэшируются — страницы кабинета динамические и всегда читают свежее.
 */

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function proxy(request: Request, params: Promise<{ path: string[] }>) {
  if (!BACKEND) {
    return NextResponse.json(
      { error: "BACKEND_URL не задан. Кабинет работает только вместе с бэкендом." },
      { status: 503 },
    );
  }

  const { path } = await params;
  const token = request.headers
    .get("cookie")
    ?.split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(`${CORP_COOKIE}=`))
    ?.slice(CORP_COOKIE.length + 1);

  if (!token) {
    return NextResponse.json({ error: "Нужно войти" }, { status: 401 });
  }

  const search = new URL(request.url).search;
  const target = `${BACKEND}/api/corp/${path.join("/")}${search}`;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  const method = request.method;
  const body = MUTATING.has(method) ? await request.arrayBuffer() : undefined;

  const res = await fetch(target, {
    method,
    headers,
    body: body && body.byteLength > 0 ? body : undefined,
    cache: "no-store",
  }).catch(() => null);

  if (!res) {
    return NextResponse.json({ error: "Сервер недоступен" }, { status: 502 });
  }

  if (res.status === 204) return new NextResponse(null, { status: 204 });

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(request, ctx.params);
}
export async function POST(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(request, ctx.params);
}
export async function PATCH(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(request, ctx.params);
}
export async function DELETE(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(request, ctx.params);
}
