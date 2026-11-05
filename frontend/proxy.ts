import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { counterpart, langOf } from "@/lib/routes";

/**
 * Ранняя проверка входа в закрытые разделы.
 *
 * Зачем это здесь, а не только на страницах. У админки и кабинета появился
 * каркас загрузки (loading.tsx), а он включает потоковую отдачу: заголовки
 * ответа уходят раньше, чем страница успевает вызвать redirect. В итоге
 * закрытый раздел без входа отвечал кодом 200 с пустым каркасом вместо
 * честного перенаправления — данные не утекали, но выглядело так, будто
 * страница открыта всем.
 *
 * Proxy выполняется до рендера, поэтому здесь перенаправление настоящее.
 * Заодно анонимный запрос больше не доходит до бэкенда: раньше каждая
 * попытка открыть админку без входа стоила похода в базу на другом
 * континенте.
 *
 * Наличие куки — не доказательство прав. Просроченный или поддельный токен
 * тут не отличить, и это не задача этого слоя: настоящая проверка живёт на
 * странице и в бэкенде, а здесь отсекается очевидное «не входил вообще».
 */

const GUARDED = [
  { prefix: "/admin", login: "/admin/login", cookie: "airis_admin" },
  { prefix: "/corp", login: "/corp/login", cookie: "airis_corp" },
];

export function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  for (const area of GUARDED) {
    if (!pathname.startsWith(area.prefix)) continue;
    if (pathname === area.login) continue;
    if (request.cookies.get(area.cookie)?.value) continue;

    const url = request.nextUrl.clone();
    url.pathname = area.login;
    url.search = "";
    return NextResponse.redirect(url);
  }

  // Язык — после проверки входа: /admin?lang=en не должен проскочить её.
  // ?lang=en на русской странице — ссылка из WhatsApp-бота или старая
  // реклама на Европу. С 2026-11-05 у английского свои страницы (/en),
  // поэтому ведём на английскую пару, сохраняя остальные параметры: даты
  // брони, номер, utm-метки, gclid рекламы. Пары нет (оферта) — страница
  // открывается как раньше, и английский делает переводчик.
  // Временный редирект (307), а не постоянный: пары страниц могут
  // поменяться, а браузер постоянный запоминает навсегда.
  if (searchParams.get("lang") === "en" && langOf(pathname) === "ru") {
    const target = counterpart(pathname, "en");
    if (target) {
      const url = request.nextUrl.clone();
      url.pathname = target;
      url.searchParams.delete("lang");
      return NextResponse.redirect(url, 307);
    }
  }

  return NextResponse.next();
}

export const config = {
  // Закрытые разделы — всегда; публичные страницы — только когда в адресе
  // ?lang=en. Остальные запросы к сайту сюда не попадают: лишний слой на
  // каждом запросе не нужен.
  matcher: [
    "/admin/:path*",
    "/corp/:path*",
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      has: [{ type: "query", key: "lang", value: "en" }],
    },
  ],
};
