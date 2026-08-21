import { NextResponse } from "next/server";

import { isLocale } from "@/lib/corp/dictionary";
import { CORP_LANG_COOKIE, CORP_LANG_MAX_AGE } from "@/lib/corp/server";

export const runtime = "nodejs";

/**
 * Переключение языка кабинета.
 *
 * Обычная ссылка, а не кнопка со скриптом: серверные компоненты читают язык из
 * куки, поставить её должен сервер, и делать ради этого клиентский компонент с
 * router.refresh() незачем — переключатель работает даже без JavaScript.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const to = url.searchParams.get("to");
  const next = url.searchParams.get("next") || "/corp";

  // Возвращаемся только внутрь кабинета. Без этой проверки ссылку вида
  // ?next=https://чужой-сайт можно разослать сотрудникам как «ссылку на
  // кабинет», и она уведёт их наружу с нашего домена.
  const safeNext = next.startsWith("/corp") ? next : "/corp";

  const response = NextResponse.redirect(new URL(safeNext, url.origin));
  if (isLocale(to)) {
    response.cookies.set({
      name: CORP_LANG_COOKIE,
      value: to,
      httpOnly: false,
      sameSite: "lax",
      path: "/",
      maxAge: CORP_LANG_MAX_AGE,
    });
  }
  return response;
}
