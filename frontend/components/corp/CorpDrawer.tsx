"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { SignOut } from "@/components/corp/SignOut";

/**
 * Боковое меню кабинета — как в образце заказчика.
 *
 * Плитки на первом экране хороши для первого захода, но человек, который
 * работает в кабинете каждый день, не должен возвращаться на главную ради
 * перехода между разделами. Меню доступно с любой страницы.
 *
 * Разделы для ответственного и для рядового сотрудника разные: деньги и
 * коллеги — не его дело, и показывать пункты, за которыми его развернут
 * обратно, нечестно.
 *
 * Пункты приходят готовым списком, а не словарём целиком. Пропсы клиентского
 * компонента уезжают в разметку страницы: отдай сюда весь словарь — и в HTML
 * каждой страницы окажутся слова «Финансы», «Отчёты» и «Сотрудники» даже там,
 * где этих разделов у человека нет.
 */
export function CorpDrawer({
  items,
  companyName,
  userName,
  openLabel,
  closeLabel,
  signOutLabel,
}: {
  items: { href: string; label: string }[];
  companyName: string;
  userName: string;
  openLabel: string;
  closeLabel: string;
  signOutLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Переход по ссылке не размонтирует меню — закрываем сами, иначе новая
  // страница откроется под уже открытой панелью.
  useEffect(() => setOpen(false), [pathname]);

  // Пока панель открыта, страница под ней не должна прокручиваться.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);


  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={openLabel}
        aria-expanded={open}
        className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10 transition-colors hover:bg-white/16"
      >
        <span className="sr-only">{openLabel}</span>
        <svg viewBox="0 0 20 14" aria-hidden className="h-3.5 w-5 fill-none stroke-cream stroke-2">
          <path d="M0 1h20M0 7h20M0 13h20" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-50 bg-ink-950/60"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <aside className="fixed inset-y-0 left-0 z-50 flex w-[19rem] max-w-[85vw] flex-col bg-ink-950 shadow-2xl">
            <div className="flex items-start justify-between gap-3 border-b border-white/10 px-6 py-5">
              <div className="min-w-0">
                <div className="truncate text-sm text-cream">{companyName}</div>
                <div className="mt-0.5 truncate text-xs text-muted">{userName}</div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label={closeLabel}
                className="-mt-1 grid size-8 shrink-0 place-items-center rounded-lg text-muted transition-colors hover:bg-white/8 hover:text-cream"
              >
                ✕
              </button>
            </div>

            <nav className="flex-1 overflow-y-auto py-3">
              {items.map((item) => {
                const active =
                  item.href === "/corp" ? pathname === "/corp" : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    prefetch={false}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={`block px-6 py-3 text-[0.95rem] transition-colors ${
                      active
                        ? "bg-white/8 text-cream"
                        : "text-cream/75 hover:bg-white/5 hover:text-cream"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="border-t border-white/10 px-6 py-5">
              <SignOut label={signOutLabel} />
            </div>
          </aside>
        </>
      )}
    </>
  );
}
