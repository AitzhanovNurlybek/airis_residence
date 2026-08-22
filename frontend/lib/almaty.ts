/**
 * Даты и время в часовом поясе отеля.
 *
 * Сервер на Vercel живёт в UTC, браузер менеджера — в Алматы, +5 часов. Если
 * форматировать без явного пояса, сервер и клиент рисуют разный текст: React
 * ловит это как ошибку гидратации (#418), а менеджер видит время заявки,
 * сдвинутое на пять часов.
 *
 * Пояс зашит намеренно. Отель один и стоит в Алматы: и заявка, и заезд, и
 * «сегодня» считаются по его времени, кто бы и откуда ни смотрел.
 */

export const HOTEL_TZ = "Asia/Almaty";

/** Дата и время: «22.08, 14:05». */
export const hotelDateTime = new Intl.DateTimeFormat("ru-RU", {
  timeZone: HOTEL_TZ,
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/** Только дата: «22.08.2026». */
export const hotelDate = new Intl.DateTimeFormat("ru-RU", {
  timeZone: HOTEL_TZ,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

/** Сегодняшняя дата в Алматы как YYYY-MM-DD. */
export function hotelToday(): string {
  // en-CA даёт ровно ISO-подобный вид «2026-08-22» без ручной сборки строки.
  return new Intl.DateTimeFormat("en-CA", { timeZone: HOTEL_TZ }).format(new Date());
}

/**
 * Сколько суток до даты заезда по времени отеля.
 *
 * Считаем на строках «YYYY-MM-DD», а не на Date: часовой пояс уже учтён в
 * hotelToday(), а перевод в Date вернул бы смещение обратно.
 */
export function daysUntil(checkIn: string | null | undefined): number | null {
  if (!checkIn) return null;
  const target = Date.parse(`${checkIn}T00:00:00Z`);
  const today = Date.parse(`${hotelToday()}T00:00:00Z`);
  if (Number.isNaN(target) || Number.isNaN(today)) return null;
  return Math.round((target - today) / 86_400_000);
}
