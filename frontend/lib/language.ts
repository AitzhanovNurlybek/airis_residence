/**
 * Язык сайта — одно место на переключатель, перевод и форму Exely.
 *
 * Сайт переводит Google Translate: язык хранится в куке `googtrans` (её
 * читает переводчик) и в localStorage (его читает переключатель RU/KZ/EN).
 *
 * Форму брони Exely переводчик не трогает — у неё свой язык, и задаётся он
 * один раз, при запуске виджета. Раньше его брали из `<html lang>`, а этот
 * атрибут переводчик меняет только через пару секунд после загрузки, когда
 * виджет уже запущен по-русски. Повторный запуск виджет игнорирует. Итог —
 * проверено 2026-10-05: страница по-английски («Book a room»), форма
 * по-русски. Поэтому форма берёт язык отсюда, а не из атрибута.
 *
 * Ссылки из WhatsApp-бота приходят с `?lang=en|kk|ru`: гость пишет
 * по-английски — страница и форма открываются по-английски.
 */

export type Language = "ru" | "kk" | "en";

export const languageStorageKey = "airis-language";

export function isLanguage(value: unknown): value is Language {
  return value === "ru" || value === "kk" || value === "en";
}

/** Язык из адреса (`?lang=`), если он там есть и мы его знаем. */
export function languageFromUrl(): Language | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("lang");
  return isLanguage(value) ? value : null;
}

/** Сохранённый язык: сначала localStorage, потом кука переводчика. */
export function savedLanguage(): Language {
  if (typeof window === "undefined" || typeof document === "undefined") return "ru";

  try {
    const stored = window.localStorage.getItem(languageStorageKey);
    if (isLanguage(stored)) return stored;
  } catch {
    // Приватный режим или запрет хранилища — читаем куку.
  }

  const cookie = document.cookie
    .split("; ")
    .find((row) => row.startsWith("googtrans="))
    ?.split("=")[1];
  const language = cookie?.split("/").filter(Boolean).at(-1);
  return isLanguage(language) ? language : "ru";
}

/** Запомнить язык для переводчика и переключателя. */
export function saveLanguage(language: Language) {
  const value = language === "ru" ? "/ru/ru" : `/ru/${language}`;
  const expires = "expires=Fri, 31 Dec 9999 23:59:59 GMT";

  try {
    window.localStorage.setItem(languageStorageKey, language);
  } catch {
    // Без хранилища язык всё равно живёт в куке.
  }
  document.cookie = `googtrans=${value}; ${expires}; path=/`;
  document.cookie = `googtrans=${value}; ${expires}; path=/; domain=.${window.location.hostname}`;
}

/**
 * Применить `?lang=` из адреса. Вызывать ДО загрузки переводчика: он читает
 * куку при старте, и тогда страница переводится без перезагрузки.
 * Возвращает true, если язык поменялся.
 */
export function applyLanguageFromUrl(): boolean {
  const fromUrl = languageFromUrl();
  if (!fromUrl || fromUrl === savedLanguage()) return false;
  saveLanguage(fromUrl);
  return true;
}

/** На каком языке запускать форму Exely. */
export function bookingEngineLanguage(): Language {
  return languageFromUrl() ?? savedLanguage();
}
