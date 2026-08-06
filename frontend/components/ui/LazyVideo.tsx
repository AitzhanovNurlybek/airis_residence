"use client";

import { useState } from "react";

/**
 * Плеер, который ничего не грузит, пока на него не нажали.
 *
 * Два правила, из которых всё остальное следует.
 *
 * 1. До нажатия на месте плеера лежит кадр-заставка весом в десятки
 *    килобайт. Трафик хранилища ограничен, и качать ролик тем, кто до
 *    него даже не долистает, нельзя.
 * 2. Размер задаёт сам кадр. Снимают и вертикально, и горизонтально;
 *    фиксированные пропорции означали бы чёрные поля в половине случаев.
 */
export function LazyVideo({
  src,
  poster,
  label,
  className = "",
}: {
  src: string;
  poster?: string;
  label: string;
  className?: string;
}) {
  const [started, setStarted] = useState(false);

  return (
    <div
      className={`flex justify-center overflow-hidden rounded-card border border-white/10 bg-ink-950 ${className}`}
    >
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
          aria-label={label}
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
  );
}
