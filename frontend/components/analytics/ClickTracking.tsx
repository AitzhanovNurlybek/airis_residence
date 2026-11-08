"use client";

import { useEffect } from "react";

type Gtag = (...args: unknown[]) => void;

/**
 * Клики, которые для отеля почти бронь: звонок и WhatsApp.
 *
 * «Забронировать» отсюда убран 2026-11-08: событие booking_click теперь шлёт
 * сама страница брони (BookingPageEvent) — так засчитывается и поиск дат в
 * iframe Exely, который этот слушатель не видит, и нет двойного счёта.
 * Один слушатель на весь документ — кнопки разбросаны по шапке, карточкам и
 * подвалу, и метить каждую отдельно значило бы однажды забыть новую.
 */
export function ClickTracking() {
  useEffect(() => {
    function onClick(event: MouseEvent) {
      const link = (event.target as Element | null)?.closest?.("a");
      const href = link?.getAttribute("href") || "";
      if (!href) return;
      let name = "";
      if (href.startsWith("tel:")) name = "phone_click";
      else if (href.includes("wa.me/") || href.includes("api.whatsapp.com")) name = "whatsapp_click";
      if (!name) return;
      const gtag = (window as unknown as { gtag?: Gtag }).gtag;
      if (gtag) gtag("event", name, { link_url: href, page_path: window.location.pathname });
    }
    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, []);
  return null;
}
