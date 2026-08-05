"use client";

import Script from "next/script";
import { bookingConfig } from "@/lib/booking";

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  СЮДА ВСТАЁТ ВИДЖЕТ БАНКА ИЛИ ДВИЖКА БРОНИРОВАНИЯ                ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * Банк/интегратор обычно выдаёт одно из двух:
 *
 *   1) ССЫЛКУ на страницу бронирования или оплаты
 *      → NEXT_PUBLIC_BOOKING_MODE=engine
 *        NEXT_PUBLIC_BOOKING_URL=https://...
 *      Кнопки «Забронировать» по всему сайту начнут вести туда.
 *
 *   2) КОД ВИДЖЕТА — <script src="..."> плюс <div id="...">
 *      → NEXT_PUBLIC_BOOKING_MODE=widget
 *        NEXT_PUBLIC_BOOKING_WIDGET_SRC=https://.../widget.js
 *        NEXT_PUBLIC_BOOKING_WIDGET_HTML=<div id="booking-widget"></div>
 *      Виджет отрисуется прямо в этом блоке.
 *
 * Если ничего не задано — показывается форма заявки (ниже по странице),
 * сайт остаётся рабочим и заявки продолжают приходить.
 */
export function BookingWidgetSlot() {
  if (bookingConfig.mode !== "widget") return null;

  return (
    <div className="rounded-card border border-white/10 bg-ink-900 p-4 md:p-6">
      {bookingConfig.widgetHtml && (
        <div
          id="booking-widget-container"
          // Разметку задаёт вендор виджета через переменную окружения.
          dangerouslySetInnerHTML={{ __html: bookingConfig.widgetHtml }}
        />
      )}
      {bookingConfig.widgetScript && (
        <Script src={bookingConfig.widgetScript} strategy="afterInteractive" />
      )}
    </div>
  );
}
