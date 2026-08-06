import { cache } from "react";

import { BACKEND_URL, CONTENT_TAG } from "./rooms";

/**
 * Видеообзоры, не привязанные к номеру: кухня, лобби, общие зоны.
 *
 * Запаса в коде здесь нет намеренно: у номеров он нужен, потому что
 * без цен сайт бессмыслен, а без видео — просто на одну секцию короче.
 * Бэкенд молчит — блока не будет, ничего не сломается.
 */

export type SiteVideo = {
  slug: string;
  title: string;
  summary: string;
  video: string;
  videoPoster: string;
};

export const getSiteVideos = cache(async (): Promise<SiteVideo[]> => {
  if (!BACKEND_URL) return [];

  try {
    const res = await fetch(`${BACKEND_URL}/api/site-videos`, {
      next: { revalidate: 3600, tags: [CONTENT_TAG] },
    });
    if (!res.ok) {
      console.error("Не удалось получить видео сайта:", res.status);
      return [];
    }

    const data = await res.json();
    return Array.isArray(data) ? (data as SiteVideo[]) : [];
  } catch (e) {
    console.error("Не удалось получить видео сайта:", e);
    return [];
  }
});
