"use client";

import { useState } from "react";

/**
 * Видеообзор номера.
 *
 * Два правила, из которых всё остальное следует.
 *
 * 1. Пока гость не нажал «play», ролик не грузится вообще: на его месте
 *    лежит кадр-заставка весом в десятки килобайт. Трафик хранилища на
 *    бесплатном тарифе ограничен, и качать видео тем, кто до него даже
 *    не долистает, нельзя.
 * 2. Размер блока задаёт сам кадр. Снимают и вертикально, и
 *    горизонтально; фиксированные пропорции означали бы чёрные поля
 *    в половине случаев.
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

      <div className="mt-6 flex justify-center overflow-hidden rounded-card border border-white/10 bg-ink-950">
        {started ? (
          <video
            src={src}
            poster={poster}
            controls
            autoPlay
            playsInline
            preload="auto"
            className="max-h-[75vh] w-auto max-w-full"
          />
        ) : (
          <button
            type="button"
            onClick={() => setStarted(true)}
            aria-label={`Смотреть видеообзор номера ${name}`}
            className="group relative block cursor-pointer"
          >
            {poster ? (
              // Обычный img, а не next/image: пропорции кадра заранее
              // неизвестны, и пусть картинка сама задаёт размер блока.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={poster}
                alt=""
                loading="lazy"
                className="max-h-[75vh] w-auto max-w-full transition-transform duration-700 group-hover:scale-[1.02]"
              />
            ) : (
              <div className="aspect-video w-full min-w-[min(100%,40rem)] bg-ink-900" />
            )}

            <span className="absolute inset-0 bg-ink-950/40 transition-colors group-hover:bg-ink-950/25" />
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
