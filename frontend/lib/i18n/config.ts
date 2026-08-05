/**
 * Языковые версии сайта.
 *
 * Русский живёт в корне (`/nomera`), остальные — с префиксом
 * (`/kk/nomera`, `/en/nomera`). Так сделано намеренно: старый сайт
 * индексировался по адресам без префикса, и менять их после индексации
 * дороже, чем оставить как есть.
 *
 * Чтобы добавить четвёртый язык: дописать код сюда, создать словарь
 * в dictionaries/ и зарегистрировать его в ../index.ts. Больше нигде
 * ничего менять не нужно.
 */

export const locales = ["ru", "kk", "en"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "ru";

/** Подписи в переключателе языков и в атрибуте lang. */
export const localeMeta: Record<Locale, { label: string; short: string; htmlLang: string }> = {
  ru: { label: "Русский", short: "RU", htmlLang: "ru" },
  kk: { label: "Қазақша", short: "KZ", htmlLang: "kk" },
  en: { label: "English", short: "EN", htmlLang: "en" },
};

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

/**
 * Адрес страницы с учётом языка.
 * Русский отдаётся без префикса, остальные — с префиксом.
 */
export function localePath(locale: Locale, path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  if (locale === defaultLocale) return clean;
  return clean === "/" ? `/${locale}` : `/${locale}${clean}`;
}

/** Обратная операция: убрать языковой префикс из адреса. */
export function stripLocale(pathname: string): { locale: Locale; path: string } {
  const match = pathname.match(/^\/([a-z]{2})(\/.*)?$/);
  if (match && isLocale(match[1])) {
    return { locale: match[1], path: match[2] || "/" };
  }
  return { locale: defaultLocale, path: pathname || "/" };
}
