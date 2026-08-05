import type { MetadataRoute } from "next";
import { getRooms } from "@/lib/rooms";
import { BASE_URL } from "@/lib/seo";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const rooms = await getRooms();
  const now = new Date();

  const staticPages: { path: string; priority: number; freq: "daily" | "weekly" | "monthly" | "yearly" }[] = [
    { path: "/", priority: 1, freq: "weekly" },
    { path: "/nomera", priority: 0.9, freq: "weekly" },
    { path: "/bronirovanie", priority: 0.9, freq: "weekly" },
    { path: "/kontakty", priority: 0.7, freq: "monthly" },
    { path: "/kak-oplatit", priority: 0.6, freq: "monthly" },
    { path: "/o-kompanii", priority: 0.5, freq: "yearly" },
    { path: "/oferta", priority: 0.3, freq: "yearly" },
    { path: "/politika-konfidencialnosti", priority: 0.3, freq: "yearly" },
  ];

  return [
    ...staticPages.map((page) => ({
      url: new URL(page.path, BASE_URL).toString(),
      lastModified: now,
      changeFrequency: page.freq,
      priority: page.priority,
    })),
    ...rooms.map((room) => ({
      url: new URL(`/nomera/${room.slug}`, BASE_URL).toString(),
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
