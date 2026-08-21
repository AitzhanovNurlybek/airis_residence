"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LOCALES, LOCALE_LABELS, type Locale } from "@/lib/corp/dictionary";

/**
 * Переключатель языка кабинета.
 *
 * Клиентский только ради `usePathname`: язык ставит серверный обработчик
 * /api/corp/lang, и ему нужно знать, куда вернуть человека. Сами ссылки
 * обычные — работают и без JavaScript.
 */
export function LangSwitch({ current }: { current: Locale }) {
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-0.5 rounded-full bg-white/10 p-1">
      {LOCALES.map((locale) => {
        const active = locale === current;
        return (
          <Link
            key={locale}
            href={`/api/corp/lang?to=${locale}&next=${encodeURIComponent(pathname)}`}
            aria-current={active ? "true" : undefined}
            className={`rounded-full px-2.5 py-1 text-xs tracking-wide transition-colors ${
              active ? "bg-white text-ink-950" : "text-cream/70 hover:text-cream"
            }`}
          >
            {LOCALE_LABELS[locale]}
          </Link>
        );
      })}
    </div>
  );
}
