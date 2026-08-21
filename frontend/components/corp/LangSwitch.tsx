"use client";

import { usePathname } from "next/navigation";

import { LOCALES, LOCALE_LABELS, type Locale } from "@/lib/corp/dictionary";

/**
 * Переключатель языка кабинета.
 *
 * Клиентский только ради `usePathname`: язык ставит серверный обработчик
 * /api/corp/lang, и ему нужно знать, куда вернуть человека.
 *
 * Ссылки намеренно обычные, а не next/link. Link предзагружает адреса, а этот
 * GET меняет состояние — ставит куку языка. Предзагрузчик дёргал его сам,
 * обработчик отвечал редиректом, страница перерисовывалась, ссылки
 * предзагружались снова: получался шторм запросов, из-за которого кабинет
 * заметно тормозил. Вдобавок язык мог смениться без единого клика.
 *
 * Обычная ссылка перезагружает страницу целиком — здесь это и нужно: язык
 * читают серверные компоненты из куки, и без нового запроса он не применится.
 */
export function LangSwitch({ current }: { current: Locale }) {
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-0.5 rounded-full bg-white/10 p-1">
      {LOCALES.map((locale) => {
        const active = locale === current;
        return (
          <a
            key={locale}
            href={`/api/corp/lang?to=${locale}&next=${encodeURIComponent(pathname)}`}
            aria-current={active ? "true" : undefined}
            className={`rounded-full px-2.5 py-1 text-xs tracking-wide transition-colors ${
              active ? "bg-white text-ink-950" : "text-cream/70 hover:text-cream"
            }`}
          >
            {LOCALE_LABELS[locale]}
          </a>
        );
      })}
    </div>
  );
}
