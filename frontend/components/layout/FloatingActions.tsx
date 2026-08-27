"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import { site } from "@/lib/site";
import { getBookingHref, bookingLinkTarget } from "@/lib/booking";
import { IconPhone, IconTelegram, IconWhatsApp } from "@/components/ui/Icons";

/**
 * Мобильная панель действий снизу + мессенджеры на десктопе.
 * Появляется после первого экрана, чтобы не перекрывать hero.
 */
export function FloatingActions() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > window.innerHeight * 0.6);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      {/* Десктоп: мессенджеры сбоку */}
      <div className="pointer-events-none fixed right-6 bottom-8 z-40 hidden flex-col gap-3 md:flex be-socials">
        <AnimatePresence>
          {visible && (
            <motion.div
              className="pointer-events-auto flex flex-col gap-3"
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 30 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <a
                href={site.contacts.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Написать в WhatsApp"
                className="grid size-13 place-items-center rounded-full bg-[#25D366] text-white shadow-[0_12px_30px_-8px_rgba(37,211,102,0.6)] transition-transform can-hover:hover:scale-105"
              >
                <IconWhatsApp className="size-6" />
              </a>
              <a
                href={site.contacts.telegram}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Написать в Telegram"
                className="grid size-13 place-items-center rounded-full bg-[#29a9eb] text-white shadow-[0_12px_30px_-8px_rgba(41,169,235,0.6)] transition-transform can-hover:hover:scale-105"
              >
                <IconTelegram className="size-6" />
              </a>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Мобильные: липкая панель «Позвонить / Забронировать» */}
      <AnimatePresence>
        {visible && (
          <motion.div
            className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-ink-950/92 px-4 pt-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] backdrop-blur-xl md:hidden"
            initial={{ y: 90 }}
            animate={{ y: 0 }}
            exit={{ y: 90 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="flex gap-2.5">
              <a
                href={site.contacts.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="WhatsApp"
                className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[#25D366] text-white"
              >
                <IconWhatsApp className="size-5" />
              </a>
              <a
                href={`tel:${site.contacts.phonePrimaryRaw}`}
                aria-label="Позвонить"
                className="grid h-12 w-12 shrink-0 place-items-center rounded-full border border-sand-400/35 text-sand-200"
              >
                <IconPhone className="size-5" />
              </a>
              <a
                href={getBookingHref()}
                target={bookingLinkTarget}
                rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
                className="flex h-12 flex-1 items-center justify-center rounded-full bg-linear-to-b from-wine-500 to-wine-700 text-sm font-medium text-white"
              >
                Забронировать
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
