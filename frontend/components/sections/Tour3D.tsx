"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Hotel3D, type Cat, type CatInfo } from "@/components/hotel3d/Hotel3D";
import { SectionHead } from "@/components/ui/SectionHead";

/**
 * «Отель в 3D» прямо на главной: вход в лобби с администратором-ИИ, этажи
 * без крыши, номера изнутри.
 *
 * Сам тур подключается, только когда до него осталось ~600 px прокрутки:
 * до этого на месте один лёгкий кадр (90 КБ), и первый экран главной не
 * делит сеть и процессор с роликами тура.
 */
export function Tour3D({ cats }: { cats: Record<Cat, CatInfo> }) {
  const ref = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setNear(true);
          io.disconnect();
        }
      },
      { rootMargin: "600px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <section id="tur" className="relative scroll-mt-24 py-16 md:py-24">
      <div className="container-page">
        <SectionHead
          eyebrow="Отель в 3D"
          title="Зайдите в отель ещё до заезда"
          description="Подойдите к стойке и спросите администратора о чём угодно, снимите крышу и загляните в любой номер — днём или вечером."
          align="center"
        />

        <div ref={ref} className="mt-8 md:mt-12">
          {near ? (
            <Hotel3D cats={cats} intro={false} />
          ) : (
            <div className="relative aspect-[1920/1086] overflow-hidden rounded-card border border-white/8 bg-ink-900">
              <Image
                src="/3d/hero-night-960.webp"
                alt="Отель Airis Residence в 3D, вид сверху вечером"
                fill
                sizes="(max-width: 1280px) 100vw, 1280px"
                className="object-fill"
              />
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-sm">
          <Link
            href="/otel-3d"
            className="text-sand-200 underline-offset-4 hover:underline"
          >
            Открыть 3D на отдельной странице →
          </Link>
        </p>
      </div>
    </section>
  );
}
