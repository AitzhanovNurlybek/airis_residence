"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useSpring, useTransform } from "motion/react";

import { usePrefersReducedMotion } from "@/lib/useMediaQuery";

const shots = [
  { src: "/images/hotel/lobby.jpg", alt: "Лобби и зона отдыха Airis Residence", caption: "Лобби" },
  { src: "/images/rooms/luxe/01.jpg", alt: "Номер Comfort Plus, 30 м²", caption: "Comfort Plus · 30 м²" },
  { src: "/images/breakfast/01.jpg", alt: "Завтрак — шведский стол", caption: "Завтрак включён" },
  { src: "/images/hotel/bath-03.jpg", alt: "Ванная комната с тропическим душем", caption: "Ванная комната" },
  { src: "/images/rooms/standart-twin/01.jpg", alt: "Номер Standart Twin", caption: "Standart Twin" },
  { src: "/images/hotel/detail-01.jpg", alt: "Детали интерьера номера", caption: "Детали" },
  { src: "/images/rooms/comfort/01.jpg", alt: "Номер Comfort, 25 м²", caption: "Comfort · 25 м²" },
];

function Caption({ caption, index }: { caption: string; index: number }) {
  return (
    <figcaption className="absolute bottom-4 left-4 flex items-center gap-3 md:bottom-5 md:left-5">
      <span className="font-display text-base text-cream md:text-lg">{caption}</span>
      <span className="text-[0.7rem] text-sand-400 md:text-xs">
        {String(index + 1).padStart(2, "0")}/{String(shots.length).padStart(2, "0")}
      </span>
    </figcaption>
  );
}

function Head({ hint }: { hint: string }) {
  return (
    <div className="container-page mb-7 flex items-end justify-between gap-6 md:mb-8">
      <div>
        <p className="eyebrow">Галерея</p>
        <h2 className="mt-3 font-display text-[clamp(1.7rem,3.6vw,2.8rem)] text-cream">
          Как выглядит отель
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
export function Gallery() {
  const reduced = usePrefersReducedMotion();
  if (reduced) return <GallerySwipe />;

  return (
    <>
      <div className="lg:hidden">
        <GallerySwipe />
      </div>
      <div className="hidden lg:block">
        <GalleryScrollDriven />
      </div>
    </>
  );
}

function GallerySwipe() {
  return (
    <section aria-label="Галерея отеля" className="bg-ink-900 py-16 md:py-24">
      <Head hint="листайте вбок →" />
      {/* Отступы по краям через псевдоэлементы-распорки, чтобы снап
          не обрезал первую и последнюю карточку */}
      <div className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <span aria-hidden className="w-1 shrink-0 md:w-6" />
        {shots.map((shot, i) => (
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
            <Caption caption={shot.caption} index={i} />
          </figure>
        ))}
        <span aria-hidden className="w-1 shrink-0 md:w-6" />
      </div>
    </section>
  );
}

function GalleryScrollDriven() {
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
    <section ref={ref} aria-label="Галерея отеля" className="relative h-[320vh] bg-ink-900">
      <div className="sticky top-0 flex h-[100svh] flex-col justify-center overflow-hidden">
        <Head hint="листайте вниз →" />

        <motion.div ref={trackRef} className="flex gap-7 pl-10" style={{ x }}>
          {shots.map((shot, i) => (
            <figure
              key={shot.src}
              className="group relative h-[56vh] w-[30vw] shrink-0 overflow-hidden rounded-card border border-white/8 shadow-deep"
            >
              <Image
                src={shot.src}
                alt={shot.alt}
                fill
                sizes="32vw"
                className="object-cover transition-transform duration-700 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-linear-to-t from-ink-950/85 via-transparent to-transparent" />
              <Caption caption={shot.caption} index={i} />
            </figure>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
