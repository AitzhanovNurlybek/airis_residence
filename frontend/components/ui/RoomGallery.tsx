"use client";

import Image from "next/image";
import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import { IconClose } from "@/components/ui/Icons";

export function RoomGallery({ images, name }: { images: string[]; name: string }) {
  const [active, setActive] = useState(0);
  const [zoom, setZoom] = useState(false);

  return (
    <>
      <div className="space-y-3">
        <button
          type="button"
          onClick={() => setZoom(true)}
          className="relative block aspect-4/3 w-full cursor-zoom-in overflow-hidden rounded-card border border-white/10 shadow-lift md:shadow-deep"
          aria-label="Открыть фото на весь экран"
        >
          <AnimatePresence mode="wait">
            <motion.span
              key={images[active]}
              initial={{ opacity: 0, scale: 1.04 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="absolute inset-0"
            >
              <Image
                src={images[active]}
                alt={`${name} — фото ${active + 1}`}
                fill
                priority={active === 0}
                sizes="(max-width: 1024px) 100vw, 55vw"
                className="object-cover"
              />
            </motion.span>
          </AnimatePresence>
        </button>

        {images.length > 1 && (
          <div className="grid grid-cols-4 gap-3">
            {images.map((src, i) => (
              <button
                key={src}
                type="button"
                onClick={() => setActive(i)}
                aria-label={`Показать фото ${i + 1}`}
                aria-current={i === active}
                className={`relative aspect-4/3 overflow-hidden rounded-xl border transition-all duration-300 ${
                  i === active
                    ? "border-sand-300/70 opacity-100"
                    : "border-white/8 opacity-55 hover:opacity-85"
                }`}
              >
                <Image
                  src={src}
                  alt=""
                  fill
                  sizes="18vw"
                  className="object-cover"
                />
              </button>
            ))}
          </div>
        )}
      </div>

      <AnimatePresence>
        {zoom && (
          <motion.div
            className="fixed inset-0 z-100 grid place-items-center bg-ink-950/96 p-4 backdrop-blur-xl"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setZoom(false)}
          >
            <button
              type="button"
              aria-label="Закрыть"
              className="glass absolute top-5 right-5 grid size-11 place-items-center rounded-full text-cream"
              onClick={() => setZoom(false)}
            >
              <IconClose className="size-5" />
            </button>
            <motion.div
              className="relative h-[78svh] w-full max-w-5xl overflow-hidden rounded-card md:aspect-4/3 md:h-auto"
              initial={{ scale: 0.94, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              <Image
                src={images[active]}
                alt={`${name} — фото ${active + 1}`}
                fill
                sizes="90vw"
                className="object-contain"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
