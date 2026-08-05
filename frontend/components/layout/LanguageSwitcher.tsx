"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { localeMeta, localePath, locales, stripLocale, type Locale } from "@/lib/i18n/config";

/**
 * Переключатель языков.
 *
 * Ведёт на ту же страницу в другой языковой версии, а не на главную:
 * гость, читающий описание Luxe, при переключении должен остаться
 * на описании Luxe.
 */
export function LanguageSwitcher({
  locale,
  className = "",
}: {
  locale: Locale;
  className?: string;
}) {
  const pathname = usePathname() || "/";
  const { path } = stripLocale(pathname);

  return (
    <div
      className={`flex items-center gap-0.5 rounded-full border border-white/12 p-0.5 ${className}`}
    >
      {locales.map((item) => {
        const active = item === locale;
        return (
          <Link
            key={item}
            href={localePath(item, path)}
            hrefLang={localeMeta[item].htmlLang}
            aria-current={active ? "true" : undefined}
            title={localeMeta[item].label}
            className={`rounded-full px-2.5 py-1.5 text-[0.7rem] font-medium tracking-wide transition-colors ${
              active ? "bg-white/12 text-cream" : "text-muted hover:text-cream"
            }`}
          >
            {localeMeta[item].short}
          </Link>
        );
      })}
    </div>
  );
}
