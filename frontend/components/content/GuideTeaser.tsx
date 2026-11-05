import Link from "next/link";

import { guides } from "@/lib/articles";
import type { Lang } from "@/lib/routes";
import { Reveal } from "@/components/ui/Reveal";
import { IconArrow } from "@/components/ui/Icons";

/**
 * Путеводитель на главной: три-четыре статьи карточками.
 *
 * Нужен не только гостю. Статьи без ссылок с главной поисковик находит
 * медленно и считает второстепенными; ссылка отсюда — сигнал, что это
 * важная часть сайта.
 */
const T = {
  ru: { eyebrow: "Путеводитель", title: "Алматы: что нужно знать до поездки", all: "Весь путеводитель", hub: "/almaty" },
  en: { eyebrow: "Almaty guide", title: "Almaty: what to know before your trip", all: "The full guide", hub: "/en/almaty" },
} as const;

export function GuideTeaser({ lang = "ru" }: { lang?: Lang }) {
  const t = T[lang];
  const list = guides(lang);
  return (
    <section className="container-page py-16 md:py-24">
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">{t.eyebrow}</p>
            <h2 className="mt-4 font-display text-[clamp(1.7rem,3.4vw,2.5rem)] leading-[1.12] font-semibold text-cream">
              {t.title}
            </h2>
          </div>
          <Link href={t.hub} className="text-sm text-sand-300 underline decoration-sand-400/40 underline-offset-4 hover:text-cream">
            {t.all} →
          </Link>
        </div>
      </Reveal>
      <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {list.map((article, i) => (
          <Reveal key={article.path} delay={0.05 * i}>
            <Link
              href={article.path}
              className="group flex h-full flex-col justify-between gap-5 rounded-2xl border border-white/10 bg-ink-900 p-6 transition-colors hover:border-sand-400/40"
            >
              <span>
                <span className="block font-display text-lg leading-snug text-cream">{article.h1}</span>
                <span className="mt-2 block text-sm leading-relaxed text-muted">{article.card}</span>
              </span>
              <IconArrow className="size-5 text-sand-400 transition-transform can-hover:group-hover:translate-x-1" />
            </Link>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
