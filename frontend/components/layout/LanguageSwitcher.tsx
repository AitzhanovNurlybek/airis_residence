"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";

import { applyLanguageFromUrl, saveLanguage, savedLanguage, type Language } from "@/lib/language";
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

export function LanguageSwitcher({
  className = "",
  withGoogleElement = false,
}: {
  className?: string;
  withGoogleElement?: boolean;
}) {
  const activeLanguage = useSyncExternalStore(subscribeToLanguageChange, savedLanguage, () => "ru");

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

    if (withGoogleElement && applyLanguageFromUrl()) {
      // Кнопки RU/KZ/EN перечитают язык: событие storage в своей вкладке
      // само не приходит.
      window.dispatchEvent(new StorageEvent("storage"));
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
  }, [withGoogleElement]);

  const changeLanguage = (language: Language) => {
    saveLanguage(language);
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

  return (
    <div className={`flex items-center rounded-full border border-white/10 bg-white/5 p-1 ${className}`}>
      {withGoogleElement && <div id="google_translate_element" className="hidden" aria-hidden="true" />}
      {languages.map((language) => (
        <button
          key={language.code}
          type="button"
          onClick={() => changeLanguage(language.code)}
          aria-label={`Выбрать язык: ${language.title}`}
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
