"use client";

import { useState } from "react";
import Image from "next/image";

/**
 * Видеообзор номера.
 *
 * Пока гость не нажал «play», видео не грузится вообще: на месте плеера
 * лежит обычная фотография номера. Это не только про скорость страницы —
 * трафик хранилища на бесплатном тарифе ограничен, и качать ролик всем
 * подряд, включая тех, кто до него даже не долистает, нельзя.
 */
export function RoomVideo({
  src,
  poster,
  name,
}: {
  src: string;
  poster?: string;
  name: string;
}) {
  const [started, setStarted] = useState(false);

  return (
    <section className="mt-16">
      <h2 className="font-display text-2xl text-cream">Видеообзор номера</h2>
      <p className="mt-2 text-sm text-muted">
        Как всё выглядит на самом деле — без ретуши и удачных ракурсов.
      </p>

      <div className="relative mt-6 aspect-video overflow-hidden rounded-card border border-white/10 bg-ink-900">
        {started ? (
          <video
            src={src}
            poster={poster}
            controls
            autoPlay
            playsInline
            preload="auto"
            className="h-full w-full object-cover"
          />
        ) : (
          <button
            type="button"
            onClick={() => setStarted(true)}
            aria-label={`Смотреть видеообзор номера ${name}`}
            className="group absolute inset-0 h-full w-full cursor-pointer"
          >
            {poster && (
              <Image
                src={poster}
                alt=""
                fill
                sizes="(min-width: 1024px) 60vw, 100vw"
                className="object-cover transition-transform duration-700 group-hover:scale-[1.03]"
              />
            )}
            <span className="absolute inset-0 bg-ink-950/45 transition-colors group-hover:bg-ink-950/30" />
            <span className="absolute inset-0 grid place-items-center">
              <span className="grid h-20 w-20 place-items-center rounded-full border border-sand-200/40 bg-ink-950/60 backdrop-blur-sm transition-transform duration-300 group-hover:scale-110">
                <svg viewBox="0 0 24 24" className="ml-1 h-7 w-7 fill-sand-200" aria-hidden>
                  <path d="M8 5.5v13l11-6.5z" />
                </svg>
              </span>
            </span>
          </button>
        )}
      </div>
    </section>
  );
}
