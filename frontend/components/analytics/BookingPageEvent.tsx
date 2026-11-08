"use client";

import { useEffect } from "react";

type Gtag = (...args: unknown[]) => void;

/**
 * `booking_click` — когда гость открыл страницу бронирования.
 *
 * Сначала событие вешалось на клик по ссылке «Забронировать» (ClickTracking).
 * 2026-11-08 выяснилось, что так теряется главный путь к брони: форма поиска
 * дат на главной («Find room» / «Найти номер») — это iframe Exely, и клики
 * внутри чужого окна наш слушатель не видит. За первые 4 дня рекламы — 19
 * кликов и ноль конверсий.
 *
 * Теперь событие отправляет сама страница брони, как бы гость на неё ни
 * попал: кнопкой, формой поиска, ссылкой из бота. Это и есть «начало
 * оформления»; на клик по ссылке событие больше не шлётся, иначе один гость
 * считался бы дважды. Имя события прежнее — под ним оно импортировано в
 * Google Ads.
 *
 * gtag появляется после загрузки счётчика (afterInteractive), иногда позже,
 * чем отрисуется страница, — поэтому ждём его до 15 секунд.
 */
export function BookingPageEvent() {
  useEffect(() => {
    let tries = 0;
    const timer = window.setInterval(() => {
      const gtag = (window as unknown as { gtag?: Gtag }).gtag;
      tries += 1;
      if (gtag) {
        gtag("event", "booking_click", { page_path: window.location.pathname, method: "booking_page" });
        window.clearInterval(timer);
      } else if (tries > 50) {
        window.clearInterval(timer);
      }
    }, 300);
    return () => window.clearInterval(timer);
  }, []);
  return null;
}
