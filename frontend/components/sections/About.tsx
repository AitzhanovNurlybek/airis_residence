"use client";

import Image from "next/image";
import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

import { formatPrice, site } from "@/lib/site";
import { useIsDesktop, usePrefersReducedMotion } from "@/lib/useMediaQuery";
import { SectionHead } from "@/components/ui/SectionHead";
import { Reveal } from "@/components/ui/Reveal";

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
function CheckTimes({ floating = false }: { floating?: boolean }) {
  return (
    <div
      className={
        floating
          ? "glass absolute bottom-[8%] left-[2%] rounded-2xl px-5 py-4 shadow-lift"
          : "glass mt-4 flex items-center justify-around rounded-2xl px-5 py-4"
      }
    >
      <div className={floating ? "" : "text-center"}>
        <span className="block font-display text-2xl text-sand-200 md:text-3xl">
          {site.policy.checkIn}
        </span>
        <span className="text-[0.65rem] tracking-[0.14em] text-muted uppercase">заезд</span>
      </div>
      <div className={floating ? "mt-3" : "text-center"}>
        <span className="block font-display text-2xl text-sand-200 md:text-3xl">
          {site.policy.checkOut}
        </span>
        <span className="text-[0.65rem] tracking-[0.14em] text-muted uppercase">выезд</span>
      </div>
    </div>
  );
}

export function About() {
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
        <SectionHead
          eyebrow="Об отеле"
          title={
            <>
              {site.roomsCount} номеров, один принцип: <br className="hidden md:block" />
              <span className="text-sand-300">всё уже включено</span>
            </>
          }
          description="Airis Residence — небольшой городской отель, где не нужно доплачивать за очевидные вещи. Быстрый Wi-Fi, тишина, завтрак и круглосуточная стойка входят в стоимость номера."
        />

        <div ref={ref} className="mt-12 grid items-center gap-10 md:mt-16 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
          {/* Телефон и планшет: простая сетка из двух фото — читается сразу */}
          <div className="lg:hidden">
            <div className="grid grid-cols-5 gap-3">
              <div className="relative col-span-3 aspect-3/4 overflow-hidden rounded-card shadow-lift">
                <Image
                  src="/images/rooms/standart/01.jpg"
                  alt="Номер Standart в отеле Airis Residence"
                  fill
                  sizes="(max-width: 1024px) 55vw, 34vw"
                  className="object-cover"
                />
              </div>
              <div className="relative col-span-2 mt-8 aspect-3/4 overflow-hidden rounded-card border border-white/10 shadow-lift">
                <Image
                  src="/images/hotel/bath-01.jpg"
                  alt="Ванная комната в номере Airis Residence"
                  fill
                  sizes="(max-width: 1024px) 38vw, 26vw"
                  className="object-cover"
                />
              </div>
            </div>
            <CheckTimes />
          </div>

          {/* Десктоп: коллаж со слоями, едущими с разной скоростью */}
          <div className="relative hidden h-[38rem] lg:block">
            <motion.div
              className="absolute top-0 left-0 h-[72%] w-[68%] overflow-hidden rounded-card shadow-deep"
              style={parallax ? { y: y1, rotate } : undefined}
            >
              <Image
                src="/images/rooms/standart/01.jpg"
                alt="Номер Standart в отеле Airis Residence"
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
                alt="Ванная комната в номере Airis Residence"
                fill
                sizes="26vw"
                className="object-cover"
              />
            </motion.div>

            <CheckTimes floating />
          </div>

          <div className="space-y-8 md:space-y-10">
            {points.map((point, i) => (
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
