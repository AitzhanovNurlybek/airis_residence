"use client";

import Image from "next/image";
import { useState } from "react";
import { motion } from "motion/react";

import { SectionHead } from "@/components/ui/SectionHead";
import { IconCube } from "@/components/ui/Icons";

/**
 * Место под 3D-тур по отелю.
 *
 * ▸ Как включить: положить в .env.local
 *     NEXT_PUBLIC_TOUR_3D_URL=https://ссылка-на-тур
 *   Подойдёт любой встраиваемый тур — Kuula, Matterport, Pannellum,
 *   собственный плеер. Больше ничего менять не нужно.
 *
 * ▸ Пока ссылки нет — секция показывает превью и не выглядит «дыркой».
 */
const TOUR_URL = process.env.NEXT_PUBLIC_TOUR_3D_URL;

export function Tour3D() {
  const [loaded, setLoaded] = useState(false);

  return (
    <section id="tur" className="relative scroll-mt-24 py-20 md:py-32">
      <div className="container-page">
        <SectionHead
          eyebrow="3D-тур"
          title="Прогуляйтесь по отелю до заезда"
          description="Панорамный тур по лобби, коридорам и номерам — можно осмотреться на 360° и выбрать номер осознанно."
          align="center"
        />

        <motion.div
          className="relative mt-10 overflow-hidden rounded-card border border-white/10 shadow-deep md:mt-14"
          initial={{ opacity: 0, y: 40, rotateX: 6 }}
          whileInView={{ opacity: 1, y: 0, rotateX: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformPerspective: 1400 }}
        >
          <div className="relative aspect-4/3 sm:aspect-16/10 md:aspect-21/9">
            {TOUR_URL ? (
              <>
                <iframe
                  src={TOUR_URL}
                  title="3D-тур по отелю Airis Residence"
                  className="absolute inset-0 size-full"
                  allow="xr-spatial-tracking; gyroscope; accelerometer; fullscreen"
                  allowFullScreen
                  loading="lazy"
                  onLoad={() => setLoaded(true)}
                />
                {!loaded && (
                  <div className="absolute inset-0 grid place-items-center bg-ink-800">
                    <span className="text-sm text-muted">Загружаем тур…</span>
                  </div>
                )}
              </>
            ) : (
              <>
                <Image
                  src="/images/hotel/lobby.jpg"
                  alt="Превью 3D-тура по отелю Airis Residence"
                  fill
                  sizes="(max-width: 768px) 100vw, 80vw"
                  className="scale-105 object-cover blur-[2px]"
                />
                <div className="absolute inset-0 bg-ink-950/72" />
                <div className="absolute inset-0 grid place-items-center px-5 text-center md:px-6">
                  <div>
                    <span className="mx-auto grid size-14 place-items-center rounded-full border border-sand-400/30 bg-sand-400/8 text-sand-300 md:size-20">
                      <IconCube className="size-7 md:size-9" />
                    </span>
                    <p className="mt-4 font-display text-xl text-cream md:mt-6 md:text-3xl">
                      3D-тур скоро появится
                    </p>
                    <p className="mx-auto mt-2.5 max-w-md text-[0.82rem] leading-relaxed text-balance text-muted md:mt-3 md:text-sm">
                      Место под панорамный тур уже готово. Как только съёмка будет
                      сделана, тур встанет сюда без переделки сайта.
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
