import { NextResponse } from "next/server";

import { BACKEND_URL } from "@/lib/rooms";

/**
 * Чат с виртуальным администратором («Отель в 3D») → бэкенд /api/web-chat.
 * Через свой адрес, как отзывы: так работает и локально, и на боевом, а адрес
 * посетителя доходит до пределов частоты (X-Forwarded-For).
 */
export async function POST(request: Request) {
  if (!BACKEND_URL) {
    return NextResponse.json({ text: "", ok: false }, { status: 503 });
  }
  const body = await request.text();
  if (body.length > 4000) {
    return NextResponse.json({ text: "", ok: false }, { status: 413 });
  }
  try {
    const res = await fetch(`${BACKEND_URL}/api/web-chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
      },
      body,
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ text: "", ok: false }, { status: 502 });
  }
}
