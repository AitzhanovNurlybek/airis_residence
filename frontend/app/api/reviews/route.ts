import { NextResponse } from "next/server";

import { BACKEND_URL } from "@/lib/rooms";

/**
 * Отзыв с сайта → бэкенд. Через свой адрес, а не прямо в бэкенд: так форма
 * работает и локально, и на боевом, а адрес гостя доходит до ограничителя
 * частоты (X-Forwarded-For), иначе все гости выглядели бы одним адресом.
 */
export async function POST(request: Request) {
  if (!BACKEND_URL) {
    return NextResponse.json({ error: "Отзывы временно не принимаются" }, { status: 503 });
  }
  const body = await request.text();
  const res = await fetch(`${BACKEND_URL}/api/reviews`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
    },
    body,
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
