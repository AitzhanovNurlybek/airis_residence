"use client";

import Image from "next/image";
import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

import { site, priceFrom as fallbackPriceFrom, formatPrice } from "@/lib/site";
import { getBookingHref, bookingLinkTarget } from "@/lib/booking";
import { BookingBar } from "@/components/ui/BookingBar";
import { useIsDesktop, usePrefersReducedMotion } from "@/lib/useMediaQuery";
import { buttonClass } from "@/components/ui/Button";
import { IconCube, IconPhone, IconPin } from "@/components/ui/Icons";
import "../be-forms/be-style.css";
import { BeSearchForm } from "@/components/be-forms/BeSearchForm";
import { rooms as roomsWord } from "@/lib/plural";
import { formatPriceEn, siteEn } from "@/lib/en";
import { DirectBadge } from "@/components/ui/DirectBadge";
import type { Lang } from "@/lib/routes";

// Фон первого экрана — облёт отеля из «Отель в 3D» (2026-11-25): 5 с,
// первый и последний кадр совпадают, поэтому петля без шва. Раньше здесь было
// фото лобби под тёмной вуалью и абстрактная сцена three.js — 240 КБ
// скриптов и WebGL ради декора. Ролик весит 460 КБ (на телефоне 90 КБ),
// декодируется видеокартой и сразу показывает сам отель.
const HERO_VIDEO = "/3d/intro.mp4";
const HERO_VIDEO_MOBILE = "/3d/hero-loop-960.mp4";
const HERO_POSTER = "/3d/hero-night-960.webp";

const FACTS = {
  ru: [
    { value: `${site.roomsCount}`, label: "номеров" },
    { value: "24/7", label: "стойка регистрации" },
    { value: "0 ₸", label: "завтрак включён" },
  ],
  en: [
    { value: `${site.roomsCount}`, label: "rooms" },
    { value: "24/7", label: "front desk" },
    { value: "0 ₸", label: "breakfast included" },
  ],
};

const T = {
  ru: {
    alt: "Лобби отеля Airis Residence в Алматы",
    place: `${site.address.city}, ${site.address.street}`,
    h1a: "Отель в центре Алматы,",
    h1b: "где хочется остаться дольше",
    book: "Забронировать",
    call: `Позвонить ${site.contacts.phonePrimary}`,
  },
  en: {
    alt: "Lobby of Airis Residence hotel in Almaty",
    place: `${siteEn.address.street}, ${siteEn.address.city}`,
    h1a: "A hotel in Almaty city centre",
    h1b: "you won't want to leave",
    book: "Book now",
    call: `Call ${site.contacts.phonePrimary}`,
  },
} as const;

export function Hero({
  priceFrom = fallbackPriceFrom,
  lang = "ru",
}: {
  priceFrom?: number;
  lang?: Lang;
}) {
  const t = T[lang];
  const facts = FACTS[lang];
  const ref = useRef<HTMLElement>(null);
  // Параллакс фона отключался и раньше, а вот появление заголовка и
  // фактов ехало снизу при любом режиме: CSS-правило reduced-motion на
  // framer-motion не действует — движение тут считает JavaScript.
  // Получалось наоборот: безобидные исчезновения гасли, а именно то
  // движение, от которого укачивает, оставалось.
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
      {/* Фон: облёт отеля в 3D с параллаксом. Без анимаций (системная
          настройка) — неподвижный кадр того же вида. */}
      <motion.div
        className="absolute inset-0 -z-20"
        style={reduced ? undefined : { scale: bgScale, y: bgY }}
      >
        {reduced ? (
          <Image
            src={HERO_POSTER}
            alt={t.alt}
            fill
            priority
            sizes="100vw"
            className="object-cover object-[46%_50%]"
          />
        ) : (
          <video
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            poster={HERO_POSTER}
            aria-label={t.alt}
            className="absolute inset-0 h-full w-full object-cover object-[46%_50%]"
          >
            <source
              src={HERO_VIDEO_MOBILE}
              type="video/mp4"
              media="(max-width: 767px)"
            />
            <source src={HERO_VIDEO} type="video/mp4" />
          </video>
        )}
      </motion.div>

      {/* Затемнение: сверху под меню и снизу под текст. Середина открыта —
          отель должно быть видно. */}
      <div className="absolute inset-x-0 top-0 -z-10 h-40 bg-linear-to-b from-ink-950/80 to-transparent" />
      <div className="absolute inset-0 -z-10 bg-linear-to-t from-ink-950 via-ink-950/65 to-ink-950/10" />

      <motion.div
        className="container-page relative"
        style={parallax ? { y: contentY, opacity: contentOpacity } : undefined}
      >
        <div className="max-w-3xl">
          <motion.a
            href={
              lang === "en" ? site.address.googleMapsUrl : site.address.mapUrl
            }
            target="_blank"
            rel="noopener noreferrer"
            className="glass inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-[0.7rem] text-cream/85 transition-colors hover:text-sand-200 sm:px-4 sm:text-xs"
            initial={{ opacity: 0, y: reduced ? 0 : 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <IconPin className="size-3.5 shrink-0 text-sand-400" />
            {t.place}
          </motion.a>

          <motion.h1
            className="mt-5 font-display text-[clamp(2rem,6.4vw,5.4rem)] leading-[1.04] font-semibold tracking-[-0.02em] text-balance md:mt-6 md:leading-[0.98]"
            initial={{ opacity: 0, y: reduced ? 0 : 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="text-gradient-sand">{t.h1a}</span>{" "}
            <span className="text-cream/95">{t.h1b}</span>
          </motion.h1>

          <motion.p
            className="mt-4 max-w-xl text-[0.95rem] leading-relaxed text-cream/70 md:mt-6 md:text-lg"
            initial={{ opacity: 0, y: reduced ? 0 : 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            {lang === "en" ? (
              <>
                {site.roomsCount} rooms a short walk from Abay Avenue. Breakfast
                included, 24/7 front desk, English-speaking staff. From{" "}
                <span className="text-sand-200">
                  {formatPriceEn(priceFrom)}
                </span>{" "}
                per night.
              </>
            ) : (
              <>
                {site.roomsCount} {roomsWord(site.roomsCount)} в двух шагах от
                проспекта Абая. Завтрак включён, стойка регистрации
                круглосуточно. От{" "}
                <span className="text-sand-200">{formatPrice(priceFrom)}</span>{" "}
                за ночь.
              </>
            )}
          </motion.p>

          <motion.div
            className="mt-4"
            initial={{ opacity: 0, y: reduced ? 0 : 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.38 }}
          >
            <DirectBadge lang={lang} />
          </motion.div>

          {lang === "ru" && (
            <motion.a
              href="#tur"
              className="glass mt-4 inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm text-cream transition-colors hover:text-sand-200"
              initial={{ opacity: 0, y: reduced ? 0 : 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.9, delay: 0.42 }}
            >
              <IconCube className="size-4 text-sand-300" />
              Войти в отель в 3D и поговорить с администратором →
            </motion.a>
          )}

          <motion.dl
            className="mt-7 grid grid-cols-3 gap-4 md:mt-9 md:flex md:flex-wrap md:gap-x-10"
            initial={{ opacity: 0, y: reduced ? 0 : 20 }}
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
          className="mt-8 max-w-4xl md:mt-12 be-hidden"
          initial={{ opacity: 0, y: reduced ? 0 : 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* На телефоне форма подбора дат заняла бы весь экран — там две
              крупные кнопки, а сама форма ждёт на /bronirovanie. */}
          <div className="flex gap-2.5 sm:hidden">
            <a
              href={getBookingHref({}, lang)}
              target={bookingLinkTarget}
              rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
              className={buttonClass("primary", "lg", "flex-1")}
            >
              {t.book}
            </a>
            <a
              href={`tel:${site.contacts.phonePrimaryRaw}`}
              aria-label={t.call}
              className={buttonClass("outline", "lg", "aspect-square !px-0")}
            >
              <IconPhone className="size-5" />
            </a>
          </div>

          <div className="hidden sm:block be-hidden">
            <BookingBar />
          </div>
        </motion.div>
      </motion.div>

      <motion.div>
        <div className="container-page mt-6">
          <BeSearchForm formType={"main"} />
        </div>
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
