/**
 * Языковые версии страниц: какая русская страница чему соответствует
 * по-английски.
 *
 * Зачем английские страницы, если есть переводчик. До 2026-11-05 весь сайт
 * был русским, а английский делал Google Translate прямо в браузере. Для
 * гостя это работало, для поиска — нет: поисковик видел одну русскую
 * страницу, по запросу «hotel Almaty city centre» сайта не было вовсе, а
 * реклама на Европу вела на русский текст и стоила дороже (Google сравнивает
 * объявление со страницей). Теперь у ключевых страниц есть настоящие
 * английские версии под /en, и поисковик знает, что это пара (hreflang).
 *
 * Казахский по-прежнему делает переводчик поверх русских страниц.
 *
 * Модуль лёгкий и без контента: его читают и переключатель языка в
 * браузере, и прокси, и карта сайта.
 */

export type Lang = "ru" | "en";

export const EN_HOME = "/en";

/**
 * Пары «русская страница ↔ английская». null — у страницы нет пары:
 * оферта и политика есть только по-русски (юридический текст переводить
 * на глаз нельзя), а часть посадочных страниц написана под запросы,
 * которых в другом языке нет.
 *
 * Номера сюда не входят: у них пара считается по slug (/nomera/x ↔
 * /en/rooms/x), см. counterpart().
 */
export const PAGE_PAIRS: readonly (readonly [ru: string | null, en: string | null])[] = [
  ["/", "/en"],
  ["/nomera", "/en/rooms"],
  ["/booking", "/en/booking"],
  ["/kontakty", "/en/contacts"],
  ["/kak-oplatit", "/en/payment"],
  ["/almaty", "/en/almaty"],
  // Посадочные страницы: одна страница — один поисковый запрос.
  ["/gostinica-v-centre-almaty", "/en/almaty-city-centre-hotel"],
  ["/otel-dlya-komandirovki", "/en/business-hotel-almaty"],
  ["/gostinica-ryadom-s-centralnym-stadionom", "/en/hotel-near-central-stadium-almaty"],
  ["/gostinica-s-zavtrakom", null],
  ["/gostinica-posutochno", null],
  // Путеводитель по Алматы.
  ["/almaty/iz-aeroporta", "/en/almaty/airport-to-city-centre"],
  ["/almaty/chto-posmotret-ryadom", "/en/almaty/things-to-do-nearby"],
  ["/almaty/medeu-i-shymbulak", "/en/almaty/medeu-and-shymbulak"],
  ["/almaty/gde-ostanovitsya", "/en/almaty/where-to-stay"],
];

/** Язык страницы по её адресу. */
export function langOf(pathname: string): Lang {
  return pathname === EN_HOME || pathname.startsWith(`${EN_HOME}/`) ? "en" : "ru";
}

function clean(pathname: string): string {
  const path = pathname.split(/[?#]/)[0] || "/";
  return path.length > 1 ? path.replace(/\/+$/, "") : path;
}

/**
 * Та же страница на другом языке или null, если пары нет.
 * Для страницы на том же языке возвращает её саму.
 */
export function counterpart(pathname: string, to: Lang): string | null {
  const path = clean(pathname);
  if (langOf(path) === to) return path;

  if (to === "en") {
    const room = path.match(/^\/nomera\/([^/]+)$/);
    if (room) return `/en/rooms/${room[1]}`;
  } else {
    const room = path.match(/^\/en\/rooms\/([^/]+)$/);
    if (room) return `/nomera/${room[1]}`;
  }

  const pair = PAGE_PAIRS.find(([ru, en]) => (to === "en" ? ru : en) === path);
  if (!pair) return null;
  return to === "en" ? pair[1] : pair[0];
}

/** Главная нужного языка — куда вести, если у страницы нет пары. */
export function homeOf(lang: Lang): string {
  return lang === "en" ? EN_HOME : "/";
}

/** Путь с учётом языка: "/booking" → "/en/booking" для английского. */
export function localized(ruPath: string, lang: Lang): string {
  if (lang === "ru") return ruPath;
  return counterpart(ruPath, "en") ?? EN_HOME;
}
