import type { MetadataRoute } from "next";
import { getRooms } from "@/lib/rooms";
import { BASE_URL } from "@/lib/seo";
import { articles } from "@/lib/articles";
import { counterpart } from "@/lib/routes";

/**
 * Карта сайта. С 2026-11-05 в ней и английские страницы (/en), и
 * посадочные, и путеводитель; у страниц, у которых есть пара на другом
 * языке, указаны обе версии (hreflang) — так поисковик не считает их
 * дублями и показывает каждому его язык.
 */

type Freq = "daily" | "weekly" | "monthly" | "yearly";

const abs = (path: string) => new URL(path, BASE_URL).toString();

function entry(path: string, priority: number, freq: Freq, now: Date): MetadataRoute.Sitemap[number] {
  const ru = counterpart(path, "ru");
  const en = counterpart(path, "en");
  return {
    url: abs(path),
    lastModified: now,
    changeFrequency: freq,
    priority,
    ...(ru && en ? { alternates: { languages: { ru: abs(ru), en: abs(en), "x-default": abs(ru) } } } : {}),
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const rooms = await getRooms();
  const now = new Date();

  const staticPages: { path: string; priority: number; freq: Freq }[] = [
    { path: "/", priority: 1, freq: "weekly" },
    { path: "/nomera", priority: 0.9, freq: "weekly" },
    { path: "/booking", priority: 0.9, freq: "weekly" },
    { path: "/kontakty", priority: 0.7, freq: "monthly" },
    { path: "/kak-oplatit", priority: 0.6, freq: "monthly" },
    { path: "/korporativnym-klientam", priority: 0.7, freq: "monthly" },
    { path: "/almaty", priority: 0.6, freq: "monthly" },
    { path: "/o-kompanii", priority: 0.5, freq: "yearly" },
    { path: "/oferta", priority: 0.3, freq: "yearly" },
    { path: "/politika-konfidencialnosti", priority: 0.3, freq: "yearly" },
    { path: "/en", priority: 1, freq: "weekly" },
    { path: "/en/rooms", priority: 0.9, freq: "weekly" },
    { path: "/en/booking", priority: 0.9, freq: "weekly" },
    { path: "/en/contacts", priority: 0.7, freq: "monthly" },
    { path: "/en/payment", priority: 0.6, freq: "monthly" },
    { path: "/en/almaty", priority: 0.6, freq: "monthly" },
  ];

  return [
    ...staticPages.map((page) => entry(page.path, page.priority, page.freq, now)),
    ...rooms.flatMap((room) => [
      entry(`/nomera/${room.slug}`, 0.8, "monthly", now),
      entry(`/en/rooms/${room.slug}`, 0.8, "monthly", now),
    ]),
    ...articles.map((article) =>
      entry(article.path, article.kind === "landing" ? 0.8 : 0.6, "monthly", now),
    ),
  ];
}
