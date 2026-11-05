import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import type { Article, Block } from "@/lib/articles";
import { articleByPath } from "@/lib/articles";
import type { Room } from "@/lib/site";
import { eventVenues, formatPrice, nearby, site } from "@/lib/site";
import { eventVenuesEn, formatPriceEn, nearbyEn, roomEn } from "@/lib/en";
import { getBookingHref } from "@/lib/booking";
import { breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { BASE_URL } from "@/lib/seo";
import { homeOf, type Lang } from "@/lib/routes";

import { JsonLd } from "@/components/JsonLd";
import { Prose } from "@/components/ui/Prose";
import { buttonClass } from "@/components/ui/Button";
import { DirectBadge } from "@/components/ui/DirectBadge";
import { IconArrow, IconPhone, IconWhatsApp } from "@/components/ui/Icons";
import { Rooms } from "@/components/sections/Rooms";
import { AirportRoutes } from "@/components/sections/AirportRoutes";
import { Faq } from "@/components/sections/Faq";
import { BeSearchForm } from "@/components/be-forms/BeSearchForm";

/**
 * Страница посадочной или статьи путеводителя (lib/articles.ts).
 *
 * Текстовые блоки идут в Prose, а «живые» — номера с ценами из базы,
 * маршруты из аэропорта, площадки событий — рисуются теми же компонентами,
 * что на главной: правка в одном месте доходит до всех страниц, и цена в
 * статье не может разойтись с ценой в карточке номера.
 */

const T = {
  ru: {
    home: "Главная",
    guide: "Путеводитель",
    crumbs: "Хлебные крошки",
    book: "Забронировать",
    wa: "Написать в WhatsApp",
    faq: "Частые вопросы",
    related: "Читайте также",
    ctaTitle: "Забронировать напрямую",
    ctaText: "На официальном сайте нет наценки площадок. Оплата картой онлайн, в том числе картой иностранного банка.",
    updated: "Обновлено",
  },
  en: {
    home: "Home",
    guide: "Almaty guide",
    crumbs: "Breadcrumbs",
    book: "Book now",
    wa: "WhatsApp us",
    faq: "Frequently asked questions",
    related: "Read next",
    ctaTitle: "Book direct",
    ctaText: "No booking-site markup on the official website. Pay online by card — cards issued by foreign banks are accepted.",
    updated: "Updated",
  },
} as const;

/** Страницы, которых нет среди статей, для блока «Читайте также». */
const extraCards: Record<string, { title: string; card: string }> = {
  "/korporativnym-klientam": {
    title: "Корпоративным клиентам",
    card: "Договор, фиксированные цены, оплата по счёту и кабинет для брони сотрудников.",
  },
  "/kak-oplatit": {
    title: "Как оплатить проживание",
    card: "Способы оплаты, реквизиты, отмена брони и сроки возврата.",
  },
};

/** **жирный**, [ссылка](/путь) и {priceFrom} — больше разметки статьям не нужно. */
function inline(text: string, priceFrom: string): ReactNode[] {
  const withPrice = text.replaceAll("{priceFrom}", priceFrom);
  const parts: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|\[(.+?)\]\((.+?)\)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(withPrice))) {
    if (match.index > last) parts.push(withPrice.slice(last, match.index));
    if (match[1]) parts.push(<strong key={key++}>{match[1]}</strong>);
    else parts.push(<Link key={key++} href={match[3]}>{match[2]}</Link>);
    last = match.index + match[0].length;
  }
  if (last < withPrice.length) parts.push(withPrice.slice(last));
  return parts;
}

/** Текст без разметки — для meta, JSON-LD и подписей. */
export function plain(text: string, priceFrom: string) {
  return text
    .replaceAll("{priceFrom}", priceFrom)
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\[(.+?)\]\((.+?)\)/g, "$1");
}

function NearbyList({ lang }: { lang: Lang }) {
  const list = lang === "en" ? nearbyEn : nearby;
  return (
    <ul className="my-8 max-w-3xl divide-y divide-white/8 rounded-card border border-white/10 bg-ink-900 px-5 md:px-7">
      {list.map((place) => (
        <li key={place.name} className="flex items-baseline justify-between gap-6 py-3.5 text-sm">
          <span className="text-cream/85">{place.name}</span>
          <span className="shrink-0 text-right">
            <span className="block text-sand-400 tabular-nums">{place.distance}</span>
            {place.walk && <span className="mt-0.5 block text-xs text-muted">{place.walk}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Venues({ lang }: { lang: Lang }) {
  const list = lang === "en" ? eventVenuesEn : eventVenues;
  return (
    <ul className="my-8 grid gap-5 md:grid-cols-3">
      {list.map((venue) => (
        <li key={venue.name} className="h-full rounded-2xl border border-white/10 bg-ink-900 p-6">
          <h3 className="font-display text-lg text-cream">{venue.name}</h3>
          <p className="mt-1.5 text-xs tracking-wide text-sand-400">{venue.walk}</p>
          <p className="mt-4 text-sm leading-relaxed text-muted">{venue.note}</p>
          <ul className="mt-4 space-y-2 border-t border-white/8 pt-4">
            {venue.highlights.map((line) => (
              <li key={line} className="text-sm leading-snug text-cream/80">
                {line}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

function Cta({ lang, text, priceFrom }: { lang: Lang; text?: string; priceFrom: string }) {
  const t = T[lang];
  return (
    <div className="my-12 rounded-card border border-sand-400/25 bg-ink-900 p-6 md:p-9">
      <h2 className="font-display text-2xl font-semibold text-cream md:text-3xl">{t.ctaTitle}</h2>
      <p className="mt-3 max-w-2xl text-[0.98rem] leading-relaxed text-muted">{text ? plain(text, priceFrom) : t.ctaText}</p>
      <DirectBadge lang={lang} className="mt-5" />
      <div className="mt-7 flex flex-wrap gap-3">
        <a href={getBookingHref({}, lang)} className={buttonClass("primary", "lg", "w-full sm:w-auto")}>
          {t.book}
        </a>
        <a
          href={site.contacts.whatsapp}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonClass("outline", "lg", "w-full sm:w-auto")}
        >
          <IconWhatsApp className="size-4" />
          {t.wa}
        </a>
        <a href={`tel:${site.contacts.phonePrimaryRaw}`} className={buttonClass("ghost", "lg", "w-full sm:w-auto")}>
          <IconPhone className="size-4" />
          {site.contacts.phonePrimary}
        </a>
      </div>
    </div>
  );
}

function TextBlock({ block, priceFrom }: { block: Block; priceFrom: string }) {
  switch (block.type) {
    case "h2":
      return <h2>{block.text}</h2>;
    case "p":
      return <p>{inline(block.text, priceFrom)}</p>;
    case "ul":
      return (
        <ul>
          {block.items.map((item) => (
            <li key={item}>{inline(item, priceFrom)}</li>
          ))}
        </ul>
      );
    case "steps":
      return (
        <ol>
          {block.items.map((step) => (
            <li key={step.title}>
              <strong>{step.title}.</strong> {inline(step.text, priceFrom)}
            </li>
          ))}
        </ol>
      );
    case "facts":
      return (
        <table>
          <tbody>
            {block.items.map(([label, value]) => (
              <tr key={label}>
                <th>{label}</th>
                <td>{inline(value, priceFrom)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    default:
      return null;
  }
}

const TEXT_TYPES = new Set(["h2", "p", "ul", "steps", "facts"]);

export function ArticlePage({ article, rooms }: { article: Article; rooms: Room[] }) {
  const lang = article.lang;
  const t = T[lang];
  const en = lang === "en";
  const shownRooms = en ? rooms.map(roomEn) : rooms;
  const min = Math.min(...rooms.map((room) => room.price));
  const priceFrom = en ? formatPriceEn(min) : formatPrice(min);

  // Подряд идущие текстовые блоки — в одну «прозу», живые блоки — отдельно.
  const groups: (Block[] | Block)[] = [];
  for (const block of article.blocks) {
    if (TEXT_TYPES.has(block.type)) {
      const tail = groups.at(-1);
      if (Array.isArray(tail)) tail.push(block);
      else groups.push([block]);
    } else {
      groups.push(block);
    }
  }

  const hub = en ? "/en/almaty" : "/almaty";
  const crumbs = [
    { name: t.home, path: homeOf(lang) },
    ...(article.kind === "guide" ? [{ name: t.guide, path: hub }] : []),
    { name: plain(article.h1, priceFrom), path: article.path },
  ];

  return (
    <>
      <JsonLd data={breadcrumbJsonLd(crumbs)} />
      {article.faq && <JsonLd data={faqJsonLd(article.faq.map((item) => ({ q: plain(item.q, priceFrom), a: plain(item.a, priceFrom) })))} />}
      {article.kind === "guide" && (
        <JsonLd
          data={{
            "@context": "https://schema.org",
            "@type": "Article",
            headline: plain(article.h1, priceFrom),
            description: plain(article.description, priceFrom),
            inLanguage: lang,
            image: new URL(article.image, BASE_URL).toString(),
            mainEntityOfPage: new URL(article.path, BASE_URL).toString(),
            dateModified: "2026-11-05",
            author: { "@type": "Organization", name: site.name, url: BASE_URL },
            publisher: { "@id": `${BASE_URL}/#hotel` },
          }}
        />
      )}

      <div className="container-page pt-[calc(var(--header-h)+2.5rem)]">
        <nav aria-label={t.crumbs} className="text-xs text-muted">
          <ol className="flex flex-wrap items-center gap-2">
            {crumbs.map((crumb, i) => (
              <li key={crumb.path} className="flex items-center gap-2">
                {i > 0 && <span aria-hidden>/</span>}
                {i < crumbs.length - 1 ? (
                  <Link href={crumb.path} className="transition-colors hover:text-sand-300">
                    {crumb.name}
                  </Link>
                ) : (
                  <span className="text-cream/80">{crumb.name}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>

        <header className="mt-8 grid items-center gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:gap-14">
          <div>
            <p className="eyebrow">{article.eyebrow}</p>
            <h1 className="mt-4 font-display text-[clamp(2.1rem,4.6vw,3.4rem)] leading-[1.05] font-semibold text-cream">
              {plain(article.h1, priceFrom)}
            </h1>
            <p className="mt-5 text-[1.05rem] leading-relaxed text-cream/75">{inline(article.lead, priceFrom)}</p>
            {article.kind === "landing" && (
              <>
                <DirectBadge lang={lang} className="mt-6" />
                <div className="mt-6 flex flex-wrap gap-3">
                  <a href={getBookingHref({}, lang)} className={buttonClass("primary", "lg")}>
                    {t.book}
                  </a>
                  <a href={site.contacts.whatsapp} target="_blank" rel="noopener noreferrer" className={buttonClass("outline", "lg")}>
                    <IconWhatsApp className="size-4" />
                    WhatsApp
                  </a>
                </div>
              </>
            )}
          </div>
          <div className="relative aspect-4/3 overflow-hidden rounded-card border border-white/10 shadow-deep">
            <Image
              src={article.image}
              alt={article.imageAlt}
              fill
              priority
              sizes="(max-width: 1024px) 100vw, 42vw"
              className="object-cover"
            />
          </div>
        </header>

        {article.kind === "landing" && (
          <div className="mt-12">
            <BeSearchForm />
          </div>
        )}
      </div>

      {/* Каждый блок со своим контейнером: у сетки номеров он свой внутри
          компонента, и вложенный контейнер удвоил бы поля по краям. */}
      <div className="mt-6">
        {groups.map((group, i) => {
          if (Array.isArray(group)) {
            return (
              <div key={i} className="container-page">
                <Prose>
                  {group.map((block, j) => (
                    <TextBlock key={j} block={block} priceFrom={priceFrom} />
                  ))}
                </Prose>
              </div>
            );
          }
          switch (group.type) {
            case "rooms":
              return <Rooms key={i} rooms={shownRooms} lang={lang} heading={false} />;
            case "airport":
              return (
                <div key={i} className="container-page">
                  <AirportRoutes lang={lang} />
                </div>
              );
            case "events":
              return (
                <div key={i} className="container-page">
                  <Venues lang={lang} />
                </div>
              );
            case "nearby":
              return (
                <div key={i} className="container-page">
                  <NearbyList lang={lang} />
                </div>
              );
            case "cta":
              return (
                <div key={i} className="container-page">
                  <Cta lang={lang} text={group.text} priceFrom={priceFrom} />
                </div>
              );
            default:
              return null;
          }
        })}
      </div>

      {article.faq && (
        <Faq
          lang={lang}
          title={t.faq}
          items={article.faq.map((item) => ({ q: plain(item.q, priceFrom), a: plain(item.a, priceFrom) }))}
        />
      )}

      <section className="container-page pb-8">
        <h2 className="font-display text-2xl text-cream md:text-3xl">{t.related}</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {article.related.map((path) => {
            const other = articleByPath(path);
            const card = other ? { title: plain(other.h1, priceFrom), card: other.card } : extraCards[path];
            if (!card) return null;
            return (
              <Link
                key={path}
                href={path}
                className="group flex h-full flex-col justify-between gap-5 rounded-2xl border border-white/10 bg-ink-900 p-6 transition-colors hover:border-sand-400/40"
              >
                <span>
                  <span className="block font-display text-xl leading-snug text-cream">{card.title}</span>
                  <span className="mt-2 block text-sm leading-relaxed text-muted">{card.card}</span>
                </span>
                <IconArrow className="size-5 text-sand-400 transition-transform can-hover:group-hover:translate-x-1" />
              </Link>
            );
          })}
        </div>
      </section>
    </>
  );
}

/** Метаданные статьи: цена «от» — из базы, как на самой странице. */
export async function articleMetadata(article: Article) {
  const { getPriceFrom } = await import("@/lib/rooms");
  const { pageMetadata } = await import("@/lib/seo");
  const min = await getPriceFrom();
  const priceFrom = article.lang === "en" ? formatPriceEn(min) : formatPrice(min);
  return pageMetadata({
    title: plain(article.title, priceFrom),
    description: plain(article.description, priceFrom),
    path: article.path,
    image: article.image,
  });
}
