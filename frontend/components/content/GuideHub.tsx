import Image from "next/image";
import Link from "next/link";

import { guides, landings } from "@/lib/articles";
import { breadcrumbJsonLd } from "@/lib/seo";
import { homeOf, type Lang } from "@/lib/routes";
import { JsonLd } from "@/components/JsonLd";
import { PageHeader } from "@/components/ui/Prose";
import { IconArrow } from "@/components/ui/Icons";

/** Оглавление путеводителя: статьи о городе и страницы «где остановиться». */
const T = {
  ru: {
    home: "Главная",
    eyebrow: "Путеводитель",
    title: "Путеводитель по Алматы",
    description:
      "Как добраться из аэропорта, что посмотреть в центре, как поехать в горы и какой район выбрать. Написано отелем в центре города — по тем вопросам, которые гости задают нам чаще всего.",
    stay: "Остановиться в центре",
  },
  en: {
    home: "Home",
    eyebrow: "Almaty guide",
    title: "Almaty travel guide",
    description:
      "Getting in from the airport, what to see in the centre, a day in the mountains and which area to stay in. Written by a hotel in the city centre, answering the questions our guests ask most.",
    stay: "Staying in the centre",
  },
} as const;

export function GuideHub({ lang }: { lang: Lang }) {
  const t = T[lang];
  const path = lang === "en" ? "/en/almaty" : "/almaty";
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: t.home, path: homeOf(lang) },
          { name: t.eyebrow, path },
        ])}
      />
      <div className="container-page pt-[calc(var(--header-h)+3rem)] pb-8">
        <PageHeader eyebrow={t.eyebrow} title={t.title} description={t.description} />

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {guides(lang).map((article) => (
            <Link
              key={article.path}
              href={article.path}
              className="group overflow-hidden rounded-card border border-white/10 bg-ink-900 transition-colors hover:border-sand-400/40"
            >
              <div className="relative aspect-16/9 overflow-hidden">
                <Image
                  src={article.image}
                  alt={article.imageAlt}
                  fill
                  sizes="(max-width: 768px) 100vw, 50vw"
                  className="object-cover transition-transform duration-700 can-hover:group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-linear-to-t from-ink-950/80 to-transparent" />
              </div>
              <div className="p-6 md:p-7">
                <h2 className="font-display text-2xl leading-snug text-cream">{article.h1}</h2>
                <p className="mt-2 text-sm leading-relaxed text-muted">{article.card}</p>
                <IconArrow className="mt-5 size-5 text-sand-400 transition-transform can-hover:group-hover:translate-x-1" />
              </div>
            </Link>
          ))}
        </div>

        <h2 className="mt-20 font-display text-2xl text-cream md:text-3xl">{t.stay}</h2>
        <ul className="mt-6 grid gap-3 md:grid-cols-2">
          {landings(lang).map((article) => (
            <li key={article.path}>
              <Link
                href={article.path}
                className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 px-5 py-4 text-cream transition-colors hover:border-sand-400/40"
              >
                <span>
                  <span className="block">{article.h1}</span>
                  <span className="mt-1 block text-xs text-muted">{article.card}</span>
                </span>
                <IconArrow className="size-4 shrink-0 text-sand-400" />
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
