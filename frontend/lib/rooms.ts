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
 * ── Почему данные не кэшируются ──────────────────────────────────
 * Пробовали ISR с тегами: цена менялась в базе, но посетитель ещё
 * какое-то время видел старую — Next отдаёт устаревшую страницу и
 * лишь запускает пересборку в фоне. Для админки это выглядит как
 * «сохранил, а на сайте по-старому», и никакой прогрев кэша не даёт
 * стабильного результата: момент готовности страницы не контролируется.
 *
 * Поэтому страницы рендерятся на каждый запрос. Цена этого — один
 * запрос к своему же бэкенду (миллисекунды), выгода — то, что показано
 * на сайте, всегда совпадает с тем, что в админке. Для отеля на
 * несколько десятков номеров это правильный размен.
 */

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
    const res = await fetch(`${BACKEND_URL}/api/rooms`, { cache: "no-store" });
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
