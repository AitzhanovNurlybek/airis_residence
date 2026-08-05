"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import { SectionHead } from "@/components/ui/SectionHead";
import { Reveal } from "@/components/ui/Reveal";
import { faqItems } from "@/lib/faq";

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="relative py-20 md:py-32">
      <div className="container-page max-w-4xl">
        <SectionHead eyebrow="Вопросы" title="Частые вопросы" align="center" />

        <div className="mt-12 divide-y divide-white/8 border-y border-white/8">
          {faqItems.map((item, i) => {
            const isOpen = open === i;
            return (
              <Reveal key={item.q} delay={i * 0.04} depth={false}>
                <h3>
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : i)}
                    aria-expanded={isOpen}
                    className="flex w-full items-center justify-between gap-4 py-5 text-left md:gap-6 md:py-6"
                  >
                    <span
                      className={`font-display text-base transition-colors sm:text-lg md:text-xl ${
                        isOpen ? "text-sand-200" : "text-cream"
                      }`}
                    >
                      {item.q}
                    </span>
                    <span
                      className={`grid size-8 shrink-0 place-items-center rounded-full border transition-all duration-300 ${
                        isOpen
                          ? "rotate-45 border-sand-300/60 text-sand-200"
                          : "border-white/15 text-muted"
                      }`}
                    >
                      <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                        <path d="M12 5v14M5 12h14" />
                      </svg>
                    </span>
                  </button>
                </h3>

                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                      className="overflow-hidden"
                    >
                      <p className="pb-5 text-[0.9rem] leading-relaxed text-muted md:pr-12 md:pb-6 md:text-[0.95rem]">
                        {item.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
