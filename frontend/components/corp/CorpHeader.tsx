import Link from "next/link";

import { CorpDrawer } from "@/components/corp/CorpDrawer";
import { LangSwitch } from "@/components/corp/LangSwitch";
import { Logo } from "@/components/ui/Logo";
import type { Dictionary, Locale } from "@/lib/corp/dictionary";

/**
 * Шапка кабинета. Тёмная, как на сайте, чтобы человек видел: это тот же отель,
 * просто закрытый раздел. Ниже светлый фон — рабочая часть, где читают таблицы.
 */
export function CorpHeader({
  dict,
  locale,
  companyName,
  userName,
  signedIn = true,
  isAdmin = false,
}: {
  dict: Dictionary;
  locale: Locale;
  companyName?: string;
  userName?: string;
  /** На форме входа ссылок в кабинет и кнопки выхода быть не должно. */
  signedIn?: boolean;
  /** Ответственному в меню доступны деньги, отчёты и сотрудники. */
  isAdmin?: boolean;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-ink-950">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-5 md:px-8">
        {signedIn && (
          <CorpDrawer
            items={[
              { href: "/corp", label: dict.nav.cabinet },
              { href: "/corp/booking", label: dict.cabinet.tiles.book },
              { href: "/corp/bookings", label: dict.cabinet.tiles.bookings },
              // Разделы, которых у рядового сотрудника нет, сюда не попадают
              // вовсе — не только скрыты, но и отсутствуют в разметке.
              ...(isAdmin
                ? [
                    { href: "/corp/finance", label: dict.cabinet.tiles.finance },
                    { href: "/corp/reports", label: dict.cabinet.tiles.reports },
                    { href: "/corp/employees", label: dict.cabinet.tiles.employees },
                  ]
                : []),
            ]}
            companyName={companyName ?? dict.brand}
            userName={userName ?? ""}
            openLabel={dict.nav.cabinet}
            closeLabel={dict.nav.back}
            signOutLabel={dict.nav.signOut}
          />
        )}
        {/* prefetch выключен по всему кабинету. Каждая его страница
            динамическая и ходит в базу; предзагрузка означала бы рендер на
            сервере с запросом через полмира на каждое наведение мыши. */}
        <Link href="/corp" prefetch={false} className="shrink-0" aria-label={dict.brand}>
          <Logo className="h-8 w-auto" />
        </Link>

        <div className="ml-auto flex items-center gap-3 md:gap-5">
          {companyName && (
            <span className="hidden max-w-[16rem] truncate text-xs text-muted md:block">
              {companyName}
              {userName ? ` · ${userName}` : ""}
            </span>
          )}
          {/* «Кабинет» и «Выход» переехали в боковое меню — в шапке они
              дублировали бы его и отнимали место у названия компании. */}
          <LangSwitch current={locale} />
        </div>
      </div>
    </header>
  );
}
