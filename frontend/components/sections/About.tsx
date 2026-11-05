"use client";

import Image from "next/image";
import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

import { formatPrice, site } from "@/lib/site";
import { useIsDesktop, usePrefersReducedMotion } from "@/lib/useMediaQuery";
import { SectionHead } from "@/components/ui/SectionHead";
import { Reveal } from "@/components/ui/Reveal";
import { rooms as roomsWord } from "@/lib/plural";
import { formatPriceEn } from "@/lib/en";
import type { Lang } from "@/lib/routes";

const pointsEn = [
  {
    title: "Central, but quiet",
    text: "134/2 Nauryzbai Batyr St. — 800 metres to Abay Avenue and 700 to Baikonur metro station. The building sits in a closed courtyard, away from the traffic.",
  },
  {
    title: "24/7 front desk",
    text: `Check-in from ${site.policy.checkIn}, check-out until ${site.policy.checkOut}. There is always someone at the desk at night. The team speaks Russian, English and Turkish. Early check-in and late check-out cost ${formatPriceEn(site.policy.earlyCheckInFee)}, if the room is free.`,
  },
  {
    title: "Breakfast already in the price",
    text: "A buffet every morning: hot dishes, pastries, fruit, cheese, and a halal option. No need to look for a café or pay a separate bill.",
  },
];

const points = [
  {
    title: "Центр, но без шума",
    text: "Наурызбай батыра 134/2 — 800 метров до проспекта Абая и 700 до метро «Байконур». Двор закрытый, окна выходят не на трассу.",
  },
  {
    title: "Стойка регистрации 24/7",
    text: `Заезд с ${site.policy.checkIn}, выезд до ${site.policy.checkOut}. Ночью на стойке всегда есть сотрудник. Ранний заезд и поздний выезд — ${formatPrice(site.policy.earlyCheckInFee)}, если номер свободен.`,
  },
  {
    title: "Завтрак уже в цене",
    text: "Шведский стол каждое утро: горячее, выпечка, фрукты, сыры. Не нужно искать кафе и считать чек отдельно.",
  },
];

/** Время заезда и выезда — на десктопе плашка поверх коллажа, на телефоне строка. */
function CheckTimes({ floating = false, lang = "ru" }: { floating?: boolean; lang?: Lang }) {
  const en = lang === "en";
  return (
    <div
      className={
        floating
          ? "glass absolute bottom-[8%] left-[2%] rounded-2xl px-5 py-4 shadow-lift"
          : "glass flex items-center justify-around rounded-2xl px-5 py-4 md:mt-4"
      }
    >
      <div className={floating ? "" : "text-center"}>
        <span className="block font-display text-2xl text-sand-200 md:text-3xl">
          {site.policy.checkIn}
        </span>
        <span className="text-[0.65rem] tracking-[0.14em] text-muted uppercase">{en ? "check-in" : "заезд"}</span>
      </div>
      <div className={floating ? "mt-3" : "text-center"}>
        <span className="block font-display text-2xl text-sand-200 md:text-3xl">
          {site.policy.checkOut}
        </span>
        <span className="text-[0.65rem] tracking-[0.14em] text-muted uppercase">{en ? "check-out" : "выезд"}</span>
      </div>
    </div>
  );
}

export function About({ lang = "ru" }: { lang?: Lang }) {
  const en = lang === "en";
  const list = en ? pointsEn : points;
  const altRoom = en ? "Standart room at Airis Residence" : "Номер Standart в отеле Airis Residence";
  const altBath = en ? "Bathroom in a room at Airis Residence" : "Ванная комната в номере Airis Residence";
  const ref = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const isDesktop = useIsDesktop();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });

  const y1 = useTransform(scrollYProgress, [0, 1], ["6%", "-10%"]);
  const y2 = useTransform(scrollYProgress, [0, 1], ["-8%", "12%"]);
  const rotate = useTransform(scrollYProgress, [0, 1], [-3, 2.5]);

  const parallax = !reduced && isDesktop;

  return (
    <section id="otel" className="relative scroll-mt-24 overflow-hidden py-20 md:py-32">
      <div className="pointer-events-none absolute top-1/3 -left-40 size-[34rem] rounded-full bg-wine-700/18 blur-[140px]" />

      <div className="container-page">
        {en ? (
          <SectionHead
            eyebrow="The hotel"
            title={
              <>
                {site.roomsCount} rooms, one rule: <br className="hidden md:block" />
                <span className="text-sand-300">the basics are included</span>
              </>
            }
            description="Airis Residence is a small city hotel where you don't pay extra for the obvious. Fast Wi-Fi, quiet rooms, breakfast and a 24/7 front desk come with the room."
          />
        ) : (
          <SectionHead
            eyebrow="Об отеле"
            title={
              <>
                {site.roomsCount} {roomsWord(site.roomsCount)}, один принцип: <br className="hidden md:block" />
                <span className="text-sand-300">всё уже включено</span>
              </>
            }
            description="Airis Residence — небольшой городской отель, где не нужно доплачивать за очевидные вещи. Быстрый Wi-Fi, тишина, завтрак и круглосуточная стойка входят в стоимость номера."
          />
        )}

        <div ref={ref} className="mt-12 grid items-center gap-10 md:mt-16 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
          {/* Планшет: простая сетка из двух фото — читается сразу. На
              телефоне фото нет: блок стоит сразу под номерами, где
              фотографий уже пять, и без них он короче почти на экран.
              Остаётся время заезда и выезда — его ищут. */}
          <div className="lg:hidden">
            <div className="hidden grid-cols-5 gap-3 md:grid">
              <div className="relative col-span-3 aspect-3/4 overflow-hidden rounded-card shadow-lift">
                <Image
                  src="/images/rooms/standart/01.jpg"
                  alt={altRoom}
                  fill
                  sizes="(max-width: 1024px) 55vw, 34vw"
                  className="object-cover"
                />
              </div>
              <div className="relative col-span-2 mt-8 aspect-3/4 overflow-hidden rounded-card border border-white/10 shadow-lift">
                <Image
                  src="/images/hotel/bath-01.jpg"
                  alt={altBath}
                  fill
                  sizes="(max-width: 1024px) 38vw, 26vw"
                  className="object-cover"
                />
              </div>
            </div>
            <CheckTimes lang={lang} />
          </div>

          {/* Десктоп: коллаж со слоями, едущими с разной скоростью */}
          <div className="relative hidden h-[38rem] lg:block">
            <motion.div
              className="absolute top-0 left-0 h-[72%] w-[68%] overflow-hidden rounded-card shadow-deep"
              style={parallax ? { y: y1, rotate } : undefined}
            >
              <Image
                src="/images/rooms/standart/01.jpg"
                alt={altRoom}
                fill
                sizes="34vw"
                className="object-cover"
              />
            </motion.div>

            <motion.div
              className="absolute right-0 bottom-0 h-[62%] w-[52%] overflow-hidden rounded-card border border-white/10 shadow-deep"
              style={parallax ? { y: y2 } : undefined}
            >
              <Image
                src="/images/hotel/bath-01.jpg"
                alt={altBath}
                fill
                sizes="26vw"
                className="object-cover"
              />
            </motion.div>

            <CheckTimes floating lang={lang} />
          </div>

          <div className="space-y-8 md:space-y-10">
            {list.map((point, i) => (
              <Reveal key={point.title} delay={i * 0.1} direction="right">
                <div className="border-l border-white/10 pl-5 transition-colors hover:border-sand-400/60 md:pl-6">
                  <h3 className="font-display text-xl text-cream md:text-2xl">{point.title}</h3>
                  <p className="mt-2.5 text-[0.92rem] leading-relaxed text-muted md:mt-3 md:text-[0.95rem]">
                    {point.text}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
