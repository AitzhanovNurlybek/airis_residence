import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

import { ADMIN_COOKIE, BACKEND } from "@/lib/adminServer";
import { ROOMS_TAG } from "@/lib/rooms";

export const runtime = "nodejs";

/**
 * Прокси между админкой в браузере и FastAPI.
 *
 * Зачем он нужен, а не прямые запросы к бэкенду:
 *  · токен лежит в httpOnly-куке и не виден странице — его нельзя украсть;
 *  · браузер ходит на свой же домен, поэтому нет возни с CORS;
 *  · бэкенд не обязан быть открыт наружу — достаточно доступа с сервера.
 *
 * Сбрасывать кэш после изменений не нужно: публичные страницы читают
 * номера напрямую при каждом запросе (см. lib/rooms.ts).
 */

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function proxy(request: Request, params: Promise<{ path: string[] }>) {
  if (!BACKEND) {
    return NextResponse.json(
      { error: "BACKEND_URL не задан. Админка работает только вместе с бэкендом." },
      { status: 503 },
    );
  }

  const { path } = await params;
  const token = request.headers
    .get("cookie")
    ?.split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(`${ADMIN_COOKIE}=`))
    ?.slice(ADMIN_COOKIE.length + 1);

  if (!token) {
    return NextResponse.json({ error: "Нужно войти" }, { status: 401 });
  }

  const search = new URL(request.url).search;
  const target = `${BACKEND}/api/admin/${path.join("/")}${search}`;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  // multipart нельзя пересобирать вручную: boundary должен остаться исходным
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

  // Подстраховка на случай, когда API дёрнули в обход браузера: из
  // админки кэш гасит серверное действие refreshRoomsCache.
  //
  // Вызов с одним аргументом помечен в Next 16 как устаревший, но
  // именно он гасит запись немедленно. Форма с "max" вместо этого
  // отдаёт протухшее и обновляет в фоне — то есть ровно тот случай,
  // из-за которого кэш здесь когда-то и выключили. Когда одноаргументную
  // форму уберут, переносить сюда нечего: правки из админки закрыты
  // серверным действием, это только запасной путь.
  if (MUTATING.has(method) && res.ok) {
    (revalidateTag as unknown as (tag: string) => void)(ROOMS_TAG);
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
export async function PUT(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(request, ctx.params);
}
export async function PATCH(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(request, ctx.params);
}
export async function DELETE(request: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(request, ctx.params);
}
