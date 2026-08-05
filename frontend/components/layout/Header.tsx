"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import { site } from "@/lib/site";
import { getBookingHref, bookingLinkTarget } from "@/lib/booking";
import { localePath, type Locale } from "@/lib/i18n/config";
import type { Dictionary } from "@/lib/i18n";
import { buttonClass } from "@/components/ui/Button";
import { IconClose, IconMenu, IconPhone } from "@/components/ui/Icons";
import { Logo } from "@/components/ui/Logo";
import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";

export function Header({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  const navLinks = [
    { href: "/#nomera", label: dict.nav.rooms },
    { href: "/#otel", label: dict.nav.about },
    { href: "/#tur", label: dict.nav.tour },
    { href: "/#raspolozhenie", label: dict.nav.location },
    { href: "/kak-oplatit", label: dict.nav.payment },
    { href: "/kontakty", label: dict.nav.contacts },
  ];

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
        className={`fixed inset-x-0 top-0 z-50 transition-all duration-500 ${
          scrolled
            ? "border-b border-white/8 bg-ink-950/80 backdrop-blur-xl"
            : "border-b border-transparent bg-transparent"
        }`}
        style={{ height: "var(--header-h)" }}
      >
        <div className="container-page flex h-full items-center justify-between gap-4">
          <Link
            href={localePath(locale, "/")}
            aria-label={`${site.name} — ${dict.nav.home}`}
            className="shrink-0"
          >
            <Logo className="h-8 w-auto md:h-9" />
          </Link>

          <nav className="hidden items-center gap-6 lg:flex" aria-label={dict.nav.rooms}>
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={localePath(locale, link.href)}
                className="relative py-2 text-sm text-cream/75 transition-colors hover:text-cream after:absolute after:inset-x-0 after:-bottom-0.5 after:h-px after:origin-left after:scale-x-0 after:bg-sand-300 after:transition-transform after:duration-300 hover:after:scale-x-100"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2.5">
            <LanguageSwitcher locale={locale} className="hidden md:flex" />

            <a
              href={`tel:${site.contacts.phonePrimaryRaw}`}
              className="hidden items-center gap-2 text-sm text-cream/80 transition-colors hover:text-sand-300 xl:flex"
            >
              <IconPhone className="size-4" />
              {site.contacts.phonePrimary}
            </a>

            <a
              href={getBookingHref({}, locale)}
              target={bookingLinkTarget}
              rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
              className={buttonClass("primary", "md", "hidden sm:inline-flex")}
            >
              {dict.nav.book}
            </a>

            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label={dict.nav.openMenu}
              className="glass grid size-11 place-items-center rounded-full text-cream lg:hidden"
            >
              <IconMenu className="size-5" />
            </button>
          </div>
        </div>
      </header>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-60 overflow-y-auto overscroll-contain bg-ink-950/97 pb-10 backdrop-blur-2xl lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="container-page flex h-[var(--header-h)] items-center justify-between">
              <Logo className="h-8 w-auto" />
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label={dict.nav.closeMenu}
                className="glass grid size-11 place-items-center rounded-full text-cream"
              >
                <IconClose className="size-5" />
              </button>
            </div>

            <nav className="container-page mt-6 flex flex-col" aria-label={dict.nav.rooms}>
              {navLinks.map((link, i) => (
                <motion.div
                  key={link.href}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 + i * 0.05, duration: 0.4 }}
                >
                  <Link
                    href={localePath(locale, link.href)}
                    onClick={() => setOpen(false)}
                    className="block border-b border-white/8 py-4 font-display text-2xl text-cream sm:py-5 sm:text-3xl"
                  >
                    {link.label}
                  </Link>
                </motion.div>
              ))}
            </nav>

            <div className="container-page mt-8 space-y-3 sm:mt-10 sm:space-y-4">
              <a
                href={getBookingHref({}, locale)}
                target={bookingLinkTarget}
                rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
                onClick={() => setOpen(false)}
                className={buttonClass("primary", "lg", "w-full")}
              >
                {dict.common.bookRoom}
              </a>
              <a
                href={`tel:${site.contacts.phonePrimaryRaw}`}
                className={buttonClass("outline", "lg", "w-full")}
              >
                <IconPhone className="size-4" />
                {site.contacts.phonePrimary}
              </a>

              <div className="flex items-center justify-between gap-4 pt-2">
                <span className="text-xs tracking-[0.14em] text-muted uppercase">
                  {dict.nav.language}
                </span>
                <LanguageSwitcher locale={locale} />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
