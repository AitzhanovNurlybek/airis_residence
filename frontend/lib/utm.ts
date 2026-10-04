/**
 * Метки источника (utm_*) на время визита.
 *
 * Бот в WhatsApp присылает ссылки с метками, и виджет Exely переносит их в
 * бронь — так в кабинете Exely видно, что гость пришёл из переписки. Своей
 * аналитики на сайте нет, поэтому это единственное место, где источник брони
 * вообще записывается.
 *
 * Но гость не всегда бронирует там, куда пришёл: открыл из бота страницу
 * номера, посмотрел фото, нажал «Забронировать» — и метка потерялась бы на
 * переходе. Поэтому первая метка визита запоминается до закрытия вкладки и
 * добавляется в адрес страницы брони до запуска виджета.
 */

const KEYS = ["utm_source", "utm_medium", "utm_campaign"] as const;
const STORAGE_KEY = "airis-utm";

/** Запомнить метки из адреса, если они есть. Первые за визит не перезаписываем. */
export function rememberUtm() {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  if (!params.get("utm_source")) return;
  try {
    if (window.sessionStorage.getItem(STORAGE_KEY)) return;
    const saved: Record<string, string> = {};
    for (const key of KEYS) {
      const value = params.get(key);
      if (value) saved[key] = value.slice(0, 80);
    }
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  } catch {
    // Хранилище недоступно (приватный режим) — метка останется только в адресе.
  }
}

/**
 * Вернуть запомненные метки в адрес текущей страницы, если их там нет.
 * Вызывать перед запуском виджета Exely: он читает метки из адреса.
 */
export function restoreUtm() {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (url.searchParams.get("utm_source")) return;
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "null") as
      | Record<string, string>
      | null;
    if (!saved?.utm_source) return;
    for (const key of KEYS) {
      if (saved[key]) url.searchParams.set(key, saved[key]);
    }
    window.history.replaceState(window.history.state, "", url.toString());
  } catch {
    // Повреждённая запись или нет хранилища — просто без метки.
  }
}
