"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";

import { applyLanguageFromUrl, saveLanguage, savedLanguage, type Language } from "@/lib/language";
import { counterpart, homeOf, type Lang } from "@/lib/routes";
import { rememberUtm } from "@/lib/utm";

const languages: { code: Language; label: string; title: string }[] = [
  { code: "ru", label: "RU", title: "Русский" },
  { code: "kk", label: "KZ", title: "Қазақша" },
  { code: "en", label: "EN", title: "English" },
];

declare global {
  interface Window {
    googleTranslateElementInit?: () => void;
    google?: {
      translate?: {
        TranslateElement?: new (
          options: { pageLanguage: string; includedLanguages: string; autoDisplay: boolean },
          elementId: string,
        ) => void;
      };
    };
  }
}

function subscribeToLanguageChange(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange);
  return () => window.removeEventListener("storage", onStoreChange);
}

/** Адрес без ?lang= — язык теперь задаёт сам путь, а метки (utm) остаются. */
function keepQuery(): string {
  const params = new URLSearchParams(window.location.search);
  params.delete("lang");
  const query = params.toString();
  return `${query ? `?${query}` : ""}${window.location.hash}`;
}

/**
 * Переключатель RU / KZ / EN.
 *
 * `lang` — язык самой страницы. С 2026-11-05 английский — это отдельные
 * страницы под /en, а не перевод в браузере, поэтому:
 * - на русской странице «EN» ведёт на её английскую пару (если пары нет —
 *   как раньше, включает переводчик);
 * - на английской странице «RU» и «KZ» ведут на русскую пару, и казахский
 *   там делает переводчик;
 * - переводчик на английских страницах не грузится вовсе: переводить с
 *   русского страницу, которая уже по-английски, — испортить её.
 */
export function LanguageSwitcher({
  className = "",
  withGoogleElement = false,
  lang = "ru",
}: {
  className?: string;
  withGoogleElement?: boolean;
  lang?: Lang;
}) {
  const pathname = usePathname();
  const saved = useSyncExternalStore(subscribeToLanguageChange, savedLanguage, () => "ru" as Language);
  const activeLanguage: Language = lang === "en" ? "en" : saved;

  const buttonClasses = useMemo(
    () =>
      "h-8 min-w-9 rounded-full px-2 text-[11px] font-semibold tracking-normal transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-sand-300",
    [],
  );

  useEffect(() => {
    // Ссылка из WhatsApp-бота: ?lang=en — гость пишет по-английски. Язык
    // ставим до загрузки переводчика: он читает куку при старте, и страница
    // переводится сразу, без перезагрузки. Делает это один экземпляр — тот,
    // что держит элемент переводчика, — иначе два переключателя в шапке
    // сделали бы одно и то же дважды.
    // Метку источника (ссылка из бота) запоминаем на визит — на случай,
    // если бронировать гость пойдёт с другой страницы. См. lib/utm.ts.
    if (withGoogleElement) rememberUtm();

    if (lang === "en") {
      // Гость на английской странице — запоминаем выбор: страницы без
      // английской пары (оферта) переводчик тогда покажет по-английски.
      if (withGoogleElement && savedLanguage() !== "en") saveLanguage("en");
      return;
    }

    if (withGoogleElement && applyLanguageFromUrl()) {
      // Кнопки RU/KZ/EN перечитают язык: событие storage в своей вкладке
      // само не приходит.
      window.dispatchEvent(new StorageEvent("storage"));
    }

    if (withGoogleElement && savedLanguage() === "en") {
      // Выбран английский (раньше или ссылкой ?lang=en, которую прокси не
      // перенаправил), а у страницы есть настоящая английская версия —
      // ведём на неё вместо машинного перевода.
      const target = counterpart(window.location.pathname, "en");
      if (target) {
        window.location.replace(`${target}${keepQuery()}`);
        return;
      }
    }

    window.googleTranslateElementInit = () => {
      if (!window.google?.translate?.TranslateElement) return;

      new window.google.translate.TranslateElement(
        {
          pageLanguage: "ru",
          includedLanguages: "ru,kk,en",
          autoDisplay: false,
        },
        "google_translate_element",
      );
    };

    if (document.querySelector('script[src*="translate.google.com/translate_a/element.js"]')) {
      return;
    }

    const script = document.createElement("script");
    script.src = "//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
    script.async = true;
    document.body.appendChild(script);
  }, [withGoogleElement, lang]);

  // Переход между языками — полной загрузкой, а не роутером Next: на
  // русских страницах при старте должен подняться переводчик (он читает
  // куку только при загрузке), а на английских его быть не должно вовсе.
  /* eslint-disable @next/next/no-location-assign-relative-destination */
  const changeLanguage = (language: Language) => {
    saveLanguage(language);

    if (language === "en" && lang !== "en") {
      const target = counterpart(pathname, "en");
      if (target) {
        window.location.assign(`${target}${keepQuery()}`);
        return;
      }
    }
    if (language !== "en" && lang === "en") {
      const target = counterpart(pathname, "ru") ?? homeOf("ru");
      window.location.assign(`${target}${keepQuery()}`);
      return;
    }

    // Если страница открыта по ссылке с ?lang=, убираем его: иначе после
    // перезагрузки адрес снова выставил бы язык из ссылки, а не выбранный.
    const url = new URL(window.location.href);
    if (url.searchParams.has("lang")) {
      url.searchParams.delete("lang");
      window.location.replace(url.toString());
      return;
    }
    window.location.reload();
  };
  /* eslint-enable @next/next/no-location-assign-relative-destination */

  return (
    <div className={`flex items-center rounded-full border border-white/10 bg-white/5 p-1 ${className}`}>
      {withGoogleElement && lang === "ru" && (
        <div id="google_translate_element" className="hidden" aria-hidden="true" />
      )}
      {languages.map((language) => (
        <button
          key={language.code}
          type="button"
          onClick={() => changeLanguage(language.code)}
          aria-label={lang === "en" ? `Language: ${language.title}` : `Выбрать язык: ${language.title}`}
          aria-pressed={activeLanguage === language.code}
          className={`${buttonClasses} ${
            activeLanguage === language.code
              ? "bg-sand-300 text-ink-950"
              : "text-cream/75 hover:bg-white/8 hover:text-cream"
          }`}
        >
          {language.label}
        </button>
      ))}
    </div>
  );
}
