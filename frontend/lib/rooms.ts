import { cache } from "react";
import { rooms as fallbackRooms, type Room } from "./site";

/**
 * Источник данных о номерах.
 *
 * Если бэкенд поднят (BACKEND_URL) — номера берутся из базы, и всё,
 * что меняют в админке, попадает на сайт. Если бэкенд недоступен или
 * не настроен — отдаём зашитый в код запасной набор из lib/site.ts.
 *
 * Смысл запаса: сайт никогда не должен падать из-за админки. Упал
 * сервер с базой — гость всё равно видит номера и цены.
 *
 * ── Про кэш ──────────────────────────────────────────────────────
 * Сначала кэша не было вовсе: считалось, что запрос к своему бэкенду
 * стоит миллисекунды. По замерам он стоит ~1.9 секунды — база лежит
 * в Сиднее, и на каждую страницу заново устанавливается соединение
 * через полмира. Такой ценой платить за свежесть нельзя.
 *
 * Первая попытка кэшировать провалилась на времени жизни: Next отдаёт
 * протухшую страницу и пересобирает её в фоне, поэтому после
 * сохранения в админке гость какое-то время видел старую цену.
 *
 * Здесь другое: кэш сбрасывается не по таймеру, а в момент правки —
 * прокси админки дёргает revalidateTag("rooms") после каждого
 * изменения. Запись из кэша удаляется, и следующий запрос собирает
 * страницу заново, а не отдаёт устаревшую. Срок жизни оставлен как
 * страховка на случай, если правку сделали в обход админки.
 */

/** Общий тег кэша. Сбрасывается из app/api/admin/[...path]/route.ts. */
export const CONTENT_TAG = "rooms";

export const BACKEND_URL = (process.env.BACKEND_URL || "").replace(/\/$/, "");

type ApiRoom = Room & { sortOrder?: number; isPublished?: boolean };

function isUsable(data: unknown): data is ApiRoom[] {
  return Array.isArray(data) && data.length > 0 && typeof data[0]?.slug === "string";
}

/**
 * cache() из React убирает повторные обращения внутри одного рендера:
 * номера нужны и подвалу, и самой странице, а запрос уходит один.
 */
export const getRooms = cache(async (): Promise<Room[]> => {
  if (!BACKEND_URL) return fallbackRooms;

  try {
    const res = await fetch(`${BACKEND_URL}/api/rooms`, {
      next: { revalidate: 3600, tags: [CONTENT_TAG] },
    });
    if (!res.ok) {
      console.error("Не удалось получить номера:", res.status);
      return fallbackRooms;
    }

    const data = await res.json();
    if (!isUsable(data)) {
      console.error("API вернул пустой или неожиданный список номеров");
      return fallbackRooms;
    }
    return data;
  } catch (e) {
    console.error("Бэкенд недоступен, показываем запасной список номеров:", e);
    return fallbackRooms;
  }
});

export async function getRoomBySlug(slug: string): Promise<Room | undefined> {
  const list = await getRooms();
  return list.find((room) => room.slug === slug);
}

/** Минимальная цена по отелю — «номера от …». */
export async function getPriceFrom(): Promise<number> {
  const list = await getRooms();
  return Math.min(...list.map((room) => room.price));
}
