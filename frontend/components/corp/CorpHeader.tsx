import Link from "next/link";

import { LangSwitch } from "@/components/corp/LangSwitch";
import { SignOut } from "@/components/corp/SignOut";
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
}: {
  dict: Dictionary;
  locale: Locale;
  companyName?: string;
  userName?: string;
  /** На форме входа ссылок в кабинет и кнопки выхода быть не должно. */
  signedIn?: boolean;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-ink-950">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-5 md:px-8">
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
          {signedIn && (
            <>
              <Link
                href="/corp"
                prefetch={false}
                className="text-sm text-cream/85 transition-colors hover:text-cream"
              >
                {dict.nav.cabinet}
              </Link>
              <SignOut label={dict.nav.signOut} />
            </>
          )}
          <LangSwitch current={locale} />
        </div>
      </div>
    </header>
  );
}
