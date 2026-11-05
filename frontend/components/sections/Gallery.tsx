"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useSpring, useTransform } from "motion/react";

import { usePrefersReducedMotion } from "@/lib/useMediaQuery";
import type { Lang } from "@/lib/routes";

const shotsEn = [
  { src: "/images/hotel/lobby.jpg", alt: "Lobby and lounge at Airis Residence", caption: "Lobby" },
  { src: "/images/rooms/luxe/01.jpg", alt: "Comfort Plus room, 30 m²", caption: "Comfort Plus · 30 m²" },
  { src: "/images/breakfast/01.jpg", alt: "Breakfast buffet", caption: "Breakfast included" },
  { src: "/images/hotel/bath-03.jpg", alt: "Bathroom with a rain shower", caption: "Bathroom" },
  { src: "/images/rooms/standart-twin/01.jpg", alt: "Standart Twin room", caption: "Standart Twin" },
  { src: "/images/hotel/detail-01.jpg", alt: "Interior details in a room", caption: "Details" },
  { src: "/images/rooms/comfort/01.jpg", alt: "Comfort room, 25 m²", caption: "Comfort · 25 m²" },
];

const T = {
  ru: { eyebrow: "Галерея", title: "Как выглядит отель", aria: "Галерея отеля", side: "листайте вбок →", down: "листайте вниз →" },
  en: { eyebrow: "Gallery", title: "What the hotel looks like", aria: "Hotel gallery", side: "swipe sideways →", down: "scroll down →" },
} as const;

const shots = [
  { src: "/images/hotel/lobby.jpg", alt: "Лобби и зона отдыха Airis Residence", caption: "Лобби" },
  { src: "/images/rooms/luxe/01.jpg", alt: "Номер Comfort Plus, 30 м²", caption: "Comfort Plus · 30 м²" },
  { src: "/images/breakfast/01.jpg", alt: "Завтрак — шведский стол", caption: "Завтрак включён" },
  { src: "/images/hotel/bath-03.jpg", alt: "Ванная комната с тропическим душем", caption: "Ванная комната" },
  { src: "/images/rooms/standart-twin/01.jpg", alt: "Номер Standart Twin", caption: "Standart Twin" },
  { src: "/images/hotel/detail-01.jpg", alt: "Детали интерьера номера", caption: "Детали" },
  { src: "/images/rooms/comfort/01.jpg", alt: "Номер Comfort, 25 м²", caption: "Comfort · 25 м²" },
];

function Caption({ caption, index, total }: { caption: string; index: number; total: number }) {
  return (
    <figcaption className="absolute bottom-4 left-4 flex items-center gap-3 md:bottom-5 md:left-5">
      <span className="font-display text-base text-cream md:text-lg">{caption}</span>
      <span className="text-[0.7rem] text-sand-400 md:text-xs">
        {String(index + 1).padStart(2, "0")}/{String(total).padStart(2, "0")}
      </span>
    </figcaption>
  );
}

function Head({ hint, lang }: { hint: string; lang: Lang }) {
  return (
    <div className="container-page mb-7 flex items-end justify-between gap-6 md:mb-8">
      <div>
        <p className="eyebrow">{T[lang].eyebrow}</p>
        <h2 className="mt-3 font-display text-[clamp(1.7rem,3.6vw,2.8rem)] text-cream">
          {T[lang].title}
        </h2>
      </div>
      <span className="hidden shrink-0 text-xs tracking-[0.14em] text-muted uppercase sm:block">
        {hint}
      </span>
    </div>
  );
}

/**
 * Десктоп: секция «залипает», а лента едет вбок за вертикальной прокруткой.
 * Телефон и планшет: обычный горизонтальный свайп со снапом — привычный жест,
 * и он не отбирает у пользователя контроль над скроллом страницы.
 *
 * Выбор варианта сделан через CSS, а не через JS: иначе после гидрации
 * секция меняла бы высоту (auto ↔ 320vh) и страница дёргалась бы.
 * Скрытая ветка ничего не стоит — картинки в ней ленивые и не грузятся.
 */
export function Gallery({ lang = "ru" }: { lang?: Lang }) {
  const reduced = usePrefersReducedMotion();
  if (reduced) return <GallerySwipe lang={lang} />;

  return (
    <>
      <div className="lg:hidden">
        <GallerySwipe lang={lang} />
      </div>
      <div className="hidden lg:block">
        <GalleryScrollDriven lang={lang} />
      </div>
    </>
  );
}

function GallerySwipe({ lang }: { lang: Lang }) {
  const list = lang === "en" ? shotsEn : shots;
  return (
    <section aria-label={T[lang].aria} className="bg-ink-900 py-16 md:py-24">
      <Head hint={T[lang].side} lang={lang} />
      {/* Отступы по краям через псевдоэлементы-распорки, чтобы снап
          не обрезал первую и последнюю карточку */}
      <div className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <span aria-hidden className="w-1 shrink-0 md:w-6" />
        {list.map((shot, i) => (
          <figure
            key={shot.src}
            className="relative aspect-4/5 w-[78vw] shrink-0 snap-center overflow-hidden rounded-card border border-white/8 shadow-lift sm:aspect-4/3 sm:w-[62vw] md:w-[46vw]"
          >
            <Image
              src={shot.src}
              alt={shot.alt}
              fill
              sizes="(max-width: 640px) 78vw, (max-width: 768px) 62vw, 46vw"
              className="object-cover"
            />
            <div className="absolute inset-0 bg-linear-to-t from-ink-950/85 via-transparent to-transparent" />
            <Caption caption={shot.caption} index={i} total={list.length} />
          </figure>
        ))}
        <span aria-hidden className="w-1 shrink-0 md:w-6" />
      </div>
    </section>
  );
}

function GalleryScrollDriven({ lang }: { lang: Lang }) {
  const list = lang === "en" ? shotsEn : shots;
  const ref = useRef<HTMLElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const [travel, setTravel] = useState(0);

  // Считаем ход ленты по реальной ширине, а не процентом наугад:
  // иначе последние карточки либо не доезжают, либо уезжают в пустоту.
  useEffect(() => {
    const measure = () => {
      const track = trackRef.current;
      if (!track) return;
      setTravel(Math.max(0, track.scrollWidth - window.innerWidth + 40));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const smooth = useSpring(scrollYProgress, { stiffness: 90, damping: 26, mass: 0.4 });
  const x = useTransform(smooth, [0, 1], [0, -travel]);

  return (
    <section ref={ref} aria-label={T[lang].aria} className="relative h-[320vh] bg-ink-900">
      <div className="sticky top-0 flex h-[100svh] flex-col justify-center overflow-hidden">
        <Head hint={T[lang].down} lang={lang} />

        <motion.div ref={trackRef} className="flex gap-7 pl-10" style={{ x }}>
          {list.map((shot, i) => (
            <figure
              key={shot.src}
              className="group relative h-[56vh] w-[30vw] shrink-0 overflow-hidden rounded-card border border-white/8 shadow-deep"
            >
              <Image
                src={shot.src}
                alt={shot.alt}
                fill
                sizes="32vw"
                className="object-cover transition-transform duration-700 can-hover:group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-linear-to-t from-ink-950/85 via-transparent to-transparent" />
              <Caption caption={shot.caption} index={i} total={list.length} />
            </figure>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
