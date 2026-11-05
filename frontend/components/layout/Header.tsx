"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import { navLinks, site } from "@/lib/site";
import { navLinksEn } from "@/lib/en";
import { getBookingHref, bookingLinkTarget } from "@/lib/booking";
import { homeOf, type Lang } from "@/lib/routes";
import { buttonClass } from "@/components/ui/Button";
import { IconClose, IconMenu, IconPhone } from "@/components/ui/Icons";
import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { Logo } from "@/components/ui/Logo";

const T = {
  ru: {
    home: "на главную",
    nav: "Основная навигация",
    mobileNav: "Мобильная навигация",
    book: "Забронировать",
    bookRoom: "Забронировать номер",
    open: "Открыть меню",
    close: "Закрыть меню",
  },
  en: {
    home: "home page",
    nav: "Main navigation",
    mobileNav: "Mobile navigation",
    book: "Book now",
    bookRoom: "Book a room",
    open: "Open menu",
    close: "Close menu",
  },
} as const;

export function Header({ lang = "ru" }: { lang?: Lang }) {
  const t = T[lang];
  const links: readonly { href: string; label: string; accent?: boolean }[] = lang === "en" ? navLinksEn : navLinks;
  const bookingHref = getBookingHref({}, lang);
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      <header
        className={`fixed inset-x-0 top-0 z-50 transition-[background-color,backdrop-filter,box-shadow] duration-200 ease-airis ${
          scrolled
            ? "border-b border-white/8 bg-ink-950/80 backdrop-blur-xl"
            : "border-b border-transparent bg-transparent"
        }`}
        style={{ height: "var(--header-h)" }}
      >
        <div className="container-page flex h-full items-center justify-between gap-6">
          <Link href={homeOf(lang)} aria-label={`${site.name} — ${t.home}`} className="shrink-0">
            <Logo className="h-8 w-auto md:h-9" />
          </Link>

          <nav className="hidden items-center gap-5 xl:flex 2xl:gap-7" aria-label={t.nav}>
            {links.map((link) =>
              link.accent ? (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-full border border-sand-400/40 px-4 py-1.5 text-sm whitespace-nowrap text-sand-200 transition-colors hover:border-sand-300/70 hover:bg-sand-300/8 hover:text-cream"
                >
                  {link.label}
                </Link>
              ) : (
                <Link
                  key={link.href}
                  href={link.href}
                  className="relative py-2 text-sm whitespace-nowrap text-cream/75 transition-colors hover:text-cream after:absolute after:inset-x-0 after:-bottom-0.5 after:h-px after:origin-left after:scale-x-0 after:bg-sand-300 after:transition-transform after:duration-300 hover:after:scale-x-100"
                >
                  {link.label}
                </Link>
              ),
            )}
          </nav>

          <div className="flex items-center gap-3">
            <LanguageSwitcher className="hidden sm:flex" withGoogleElement lang={lang} />

            <a
              href={`tel:${site.contacts.phonePrimaryRaw}`}
              className="hidden items-center gap-2 text-sm whitespace-nowrap text-cream/80 transition-colors hover:text-sand-300 md:flex xl:hidden 2xl:flex"
            >
              <IconPhone className="size-4 shrink-0" />
              {site.contacts.phonePrimary}
            </a>

            <a
              href={bookingHref}
              target={bookingLinkTarget}
              rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
              className={buttonClass("primary", "md", "hidden sm:inline-flex")}
            >
              {t.book}
            </a>

            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label={t.open}
              className="glass grid size-11 place-items-center rounded-full text-cream xl:hidden"
            >
              <IconMenu className="size-5" />
            </button>
          </div>
        </div>
      </header>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-60 overflow-y-auto overscroll-contain bg-ink-950/97 pb-10 backdrop-blur-2xl xl:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="container-page flex h-[var(--header-h)] items-center justify-between">
              <Logo className="h-9 w-auto" />
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label={t.close}
                className="glass grid size-11 place-items-center rounded-full text-cream"
              >
                <IconClose className="size-5" />
              </button>
            </div>

            <nav className="container-page mt-6 flex flex-col" aria-label={t.mobileNav}>
              <LanguageSwitcher className="mb-5 w-fit" lang={lang} />

              {links.map((link, i) => (
                <motion.div
                  key={link.href}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 + i * 0.05, duration: 0.4 }}
                >
                  <Link
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className={`block border-b border-white/8 py-4 font-display text-2xl sm:py-5 sm:text-3xl ${
                      link.accent ? "text-sand-300" : "text-cream"
                    }`}
                  >
                    {link.label}
                  </Link>
                </motion.div>
              ))}
            </nav>

            <div className="container-page mt-8 space-y-3 sm:mt-10 sm:space-y-4">
              <a
                href={bookingHref}
                target={bookingLinkTarget}
                rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
                onClick={() => setOpen(false)}
                className={buttonClass("primary", "lg", "w-full")}
              >
                {t.bookRoom}
              </a>
              <a
                href={`tel:${site.contacts.phonePrimaryRaw}`}
                className={buttonClass("outline", "lg", "w-full")}
              >
                <IconPhone className="size-4 shrink-0" />
                {site.contacts.phonePrimary}
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
