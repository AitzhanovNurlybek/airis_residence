"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";

type Language = "ru" | "kk" | "en";

const languages: { code: Language; label: string; title: string }[] = [
  { code: "ru", label: "RU", title: "Русский" },
  { code: "kk", label: "KZ", title: "Қазақша" },
  { code: "en", label: "EN", title: "English" },
];

const languageStorageKey = "airis-language";

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

function readLanguageCookie(): Language {
  if (typeof window === "undefined" || typeof document === "undefined") return "ru";

  const savedLanguage = window.localStorage.getItem(languageStorageKey);
  if (savedLanguage === "kk" || savedLanguage === "en" || savedLanguage === "ru") {
    return savedLanguage;
  }

  const cookie = document.cookie
    .split("; ")
    .find((row) => row.startsWith("googtrans="))
    ?.split("=")[1];

  const language = cookie?.split("/").filter(Boolean).at(-1);
  return language === "kk" || language === "en" ? language : "ru";
}

function setTranslateCookie(language: Language) {
  const value = language === "ru" ? "/ru/ru" : `/ru/${language}`;
  const expires = "expires=Fri, 31 Dec 9999 23:59:59 GMT";

  window.localStorage.setItem(languageStorageKey, language);
  document.cookie = `googtrans=${value}; ${expires}; path=/`;
  document.cookie = `googtrans=${value}; ${expires}; path=/; domain=.${window.location.hostname}`;
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
  const activeLanguage = useSyncExternalStore(subscribeToLanguageChange, readLanguageCookie, () => "ru");

  const buttonClasses = useMemo(
    () =>
      "h-8 min-w-9 rounded-full px-2 text-[11px] font-semibold tracking-normal transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-sand-300",
    [],
  );

  useEffect(() => {
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
  }, []);

  const changeLanguage = (language: Language) => {
    setTranslateCookie(language);
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
