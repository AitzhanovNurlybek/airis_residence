import { NextResponse, type NextRequest } from "next/server";
import { defaultLocale, isLocale, locales } from "@/lib/i18n/config";

/**
 * Языковая маршрутизация.
 *
 * Русский живёт в корне: `/nomera`. Внутри Next это `/ru/nomera`,
 * но адрес в браузере остаётся коротким — делаем rewrite, а не redirect.
 * Остальные языки идут с префиксом: `/kk/nomera`, `/en/nomera`.
 *
 * Автоопределения языка по браузеру намеренно нет. Гость из-за границы,
 * открывший ссылку из письма, должен попасть ровно на ту страницу,
 * которую ему прислали, а поисковый робот — увидеть тот же адрес,
 * что и человек. Язык переключается вручную в шапке.
 */

const PUBLIC_FILE = /\.[^/]+$/;

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Служебные разделы вне языковой схемы
  if (
    pathname.startsWith("/api") ||
    pathname.startsWith("/admin") ||
    pathname.startsWith("/_next") ||
    pathname === "/robots.txt" ||
    pathname === "/sitemap.xml" ||
    PUBLIC_FILE.test(pathname)
  ) {
    return;
  }

  const firstSegment = pathname.split("/")[1];

  // /ru/... — лишний префикс: у русской версии один канонический адрес, без него
  if (firstSegment === defaultLocale) {
    const url = request.nextUrl.clone();
    url.pathname = pathname.slice(defaultLocale.length + 1) || "/";
    return NextResponse.redirect(url, 308);
  }

  // /kk/... и /en/... уже адресованы правильно
  if (isLocale(firstSegment)) return;

  // Всё остальное — русская версия, подставляем префикс незаметно
  const url = request.nextUrl.clone();
  url.pathname = `/${defaultLocale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.rewrite(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

export const supportedLocales = locales;
