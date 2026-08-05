"use client";

import Image from "next/image";
import dynamic from "next/dynamic";
import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

import { site, priceFrom as fallbackPriceFrom, formatPrice } from "@/lib/site";
import { getBookingHref, bookingLinkTarget } from "@/lib/booking";
import { BookingBar } from "@/components/ui/BookingBar";
import { useIsDesktop, usePrefersReducedMotion } from "@/lib/useMediaQuery";
import { buttonClass } from "@/components/ui/Button";
import { IconPhone, IconPin } from "@/components/ui/Icons";

// WebGL грузится только в браузере, только на десктопе и только после
// основного контента: на телефоне это лишние ~500 КБ и нагрев батареи.
const HeroScene = dynamic(() => import("@/components/three/HeroScene"), { ssr: false });

const facts = [
  { value: `${site.roomsCount}`, label: "номеров" },
  { value: "24/7", label: "стойка регистрации" },
  { value: "0 ₸", label: "завтрак включён" },
];

export function Hero({ priceFrom = fallbackPriceFrom }: { priceFrom?: number }) {
  const ref = useRef<HTMLElement>(null);
  const reduced = usePrefersReducedMotion();
  const isDesktop = useIsDesktop();

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const bgScale = useTransform(scrollYProgress, [0, 1], [1, 1.18]);
  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "14%"]);
  const contentY = useTransform(scrollYProgress, [0, 1], ["0%", "38%"]);
  const contentOpacity = useTransform(scrollYProgress, [0, 0.65], [1, 0]);

  // Параллакс контента на телефоне выключен: он съедает первый экран
  // и мешает дотянуться до кнопок при коротком свайпе.
  const parallax = !reduced && isDesktop;

  return (
    <section
      ref={ref}
      className="relative isolate flex min-h-[100svh] flex-col justify-end overflow-hidden pt-[calc(var(--header-h)+1rem)] pb-10 md:pb-20"
    >
      {/* Фон: фото лобби с параллаксом */}
      <motion.div
        className="absolute inset-0 -z-20"
        style={reduced ? undefined : { scale: bgScale, y: bgY }}
      >
        <Image
          src="/images/hotel/lobby.jpg"
          alt="Лобби отеля Airis Residence в Алматы"
          fill
          priority
          sizes="100vw"
          className="object-cover object-center"
        />
      </motion.div>

      {/* Затемнение: снизу почти в чёрный, чтобы текст читался на любом фото */}
      <div className="absolute inset-0 -z-10 bg-linear-to-b from-ink-950/88 via-ink-950/72 to-ink-950" />
      <div className="absolute inset-0 -z-10 bg-radial-[at_50%_35%] from-transparent to-ink-950/70" />
      <span className="grain-layer -z-10" />

      {/* WebGL-слой — только десктоп */}
      {parallax && (
        <div className="pointer-events-none absolute inset-0 -z-10 opacity-70 mix-blend-screen">
          <HeroScene />
        </div>
      )}

      <motion.div
        className="container-page relative"
        style={parallax ? { y: contentY, opacity: contentOpacity } : undefined}
      >
        <div className="max-w-3xl">
          <motion.a
            href={site.address.mapUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="glass inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-[0.7rem] text-cream/85 transition-colors hover:text-sand-200 sm:px-4 sm:text-xs"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <IconPin className="size-3.5 shrink-0 text-sand-400" />
            {site.address.city}, {site.address.street}
          </motion.a>

          <motion.h1
            className="mt-5 font-display text-[clamp(2rem,6.4vw,5.4rem)] leading-[1.04] font-semibold tracking-[-0.02em] text-balance md:mt-6 md:leading-[0.98]"
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="text-gradient-sand">Отель в центре Алматы,</span>{" "}
            <span className="text-cream/95">где хочется остаться дольше</span>
          </motion.h1>

          <motion.p
            className="mt-4 max-w-xl text-[0.95rem] leading-relaxed text-cream/70 md:mt-6 md:text-lg"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            {site.roomsCount} номеров в двух шагах от проспекта Абая. Завтрак включён,
            заселение круглосуточно. От{" "}
            <span className="text-sand-200">{formatPrice(priceFrom)}</span> за ночь.
          </motion.p>

          <motion.dl
            className="mt-7 grid grid-cols-3 gap-4 md:mt-9 md:flex md:flex-wrap md:gap-x-10"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.45 }}
          >
            {facts.map((fact) => (
              <div key={fact.label}>
                <dt className="sr-only">{fact.label}</dt>
                <dd>
                  <span className="block font-display text-2xl text-sand-200 md:text-3xl">
                    {fact.value}
                  </span>
                  <span className="mt-1 block text-[0.65rem] tracking-[0.14em] text-muted uppercase md:text-xs">
                    {fact.label}
                  </span>
                </dd>
              </div>
            ))}
          </motion.dl>
        </div>

        <motion.div
          className="mt-8 max-w-4xl md:mt-12"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* На телефоне форма подбора дат заняла бы весь экран — там две
              крупные кнопки, а сама форма ждёт на /bronirovanie. */}
          <div className="flex gap-2.5 sm:hidden">
            <a
              href={getBookingHref()}
              target={bookingLinkTarget}
              rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
              className={buttonClass("primary", "lg", "flex-1")}
            >
              Забронировать
            </a>
            <a
              href={`tel:${site.contacts.phonePrimaryRaw}`}
              aria-label={`Позвонить ${site.contacts.phonePrimary}`}
              className={buttonClass("outline", "lg", "aspect-square !px-0")}
            >
              <IconPhone className="size-5" />
            </a>
          </div>

          <div className="hidden sm:block">
            <BookingBar />
          </div>
        </motion.div>
      </motion.div>

      {/* Подсказка «крути вниз» */}
      <div className="pointer-events-none absolute inset-x-0 bottom-5 hidden justify-center md:flex">
        <div className="h-11 w-6 rounded-full border border-sand-300/30">
          <span
            className="mx-auto mt-2 block h-2 w-px bg-sand-300/70"
            style={{ animation: "airis-scroll-hint 2.2s ease-in-out infinite" }}
          />
        </div>
      </div>
    </section>
  );
}
