import { ru, type Dictionary } from "./dictionaries/ru";
import { kk } from "./dictionaries/kk";
import { en } from "./dictionaries/en";
import { defaultLocale, type Locale } from "./config";

export type { Dictionary };
export * from "./config";

/**
 * Словари подключены статически, а не через динамический import:
 * их немного, они небольшие, и так TypeScript ловит расхождения
 * между языками прямо при сборке.
 */
const dictionaries: Record<Locale, Dictionary> = { ru, kk, en };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] ?? dictionaries[defaultLocale];
}

/**
 * Подстановка значений в строку: t(d.hero.lead, { count: 36, price: "25 000 ₸" })
 * Плейсхолдеры пишутся как {имя}.
 */
export function t(template: string, values: Record<string, string | number> = {}): string {
  return template.replace(/\{(\w+)\}/g, (match, key) =>
    key in values ? String(values[key]) : match,
  );
}
