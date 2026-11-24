"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { motion } from "motion/react";

import { SectionHead } from "@/components/ui/SectionHead";
import { IconCube } from "@/components/ui/Icons";

/**
 * 3D-тур по отелю.
 *
 * ▸ По умолчанию — вход на собственную страницу «Отель в 3D» (/otel-3d):
 *   здание по техпаспорту, этажи без крыши, номера изнутри днём и вечером.
 *
 * ▸ Если появится сторонний панорамный тур (Kuula, Matterport, Pannellum),
 *   ссылку кладут в NEXT_PUBLIC_TOUR_3D_URL — он встанет сюда вместо превью.
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
          description="Здание в 3D по поэтажным планам: этажи без крыши и номера изнутри — выберите номер осознанно ещё до заезда."
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
              <Link
                href="/otel-3d"
                className="group absolute inset-0 block"
                aria-label="Открыть отель в 3D: этажи и номера изнутри"
              >
                <Image
                  src="/3d/hero-night.webp"
                  alt="Отель Airis Residence в 3D, вид сверху вечером"
                  fill
                  sizes="(max-width: 768px) 100vw, 80vw"
                  className="object-cover transition-transform duration-700 group-hover:scale-[1.03]"
                />
                <div className="absolute inset-0 bg-linear-to-t from-ink-950/90 via-ink-950/30 to-transparent" />
                <div className="absolute inset-x-0 bottom-0 flex flex-col items-start gap-3 p-5 md:flex-row md:items-end md:justify-between md:p-8">
                  <div>
                    <p className="flex items-center gap-2 text-[0.7rem] tracking-[0.16em] text-sand-200 uppercase">
                      <IconCube className="size-4" /> Отель в 3D
                    </p>
                    <p className="mt-2 max-w-xl font-display text-xl text-cream md:text-3xl">
                      Снимите крышу, пройдите по этажам и зайдите в любой номер
                    </p>
                    <p className="mt-2 max-w-lg text-[0.82rem] leading-relaxed text-cream/75 md:text-sm">
                      Днём или вечером — с ценой и бронированием без наценки.
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-sand-300 px-5 py-2.5 text-sm font-medium text-ink-950 transition-colors group-hover:bg-sand-200 md:px-6 md:py-3">
                    Открыть 3D →
                  </span>
                </div>
              </Link>
            )}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
