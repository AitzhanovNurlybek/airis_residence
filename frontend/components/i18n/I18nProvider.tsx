"use client";

import { createContext, useContext, type ReactNode } from "react";

import { defaultLocale, type Locale } from "@/lib/i18n/config";
import { getDictionary, type Dictionary } from "@/lib/i18n";

/**
 * Язык и словарь для клиентских компонентов.
 *
 * Серверные секции получают словарь пропсом от страницы, а клиентские
 * (там, где анимации) берут отсюда — иначе пришлось бы протаскивать
 * dict через каждый уровень вёрстки.
 */
type Value = { locale: Locale; dict: Dictionary };

const I18nContext = createContext<Value>({
  locale: defaultLocale,
  dict: getDictionary(defaultLocale),
});

export function I18nProvider({
  locale,
  dict,
  children,
}: {
  locale: Locale;
  dict: Dictionary;
  children: ReactNode;
}) {
  return <I18nContext.Provider value={{ locale, dict }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
