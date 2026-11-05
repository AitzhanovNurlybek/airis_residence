import type { Lang } from "@/lib/routes";

/**
 * «Дешевле, чем на Booking.com» — довод бронировать на сайте.
 *
 * Больше половины броней отеля приходит с Booking.com (разбор Exely за
 * 90 дней, 2026-11-04), и с каждой отель платит комиссию. Гость при этом
 * часто находит отель на сайте, а бронировать уходит туда, где привык.
 *
 * Утверждение проверяемое, а не рекламное: Booking.com продаёт номера по
 * ценам Exely плюс 12,5% (сверка 2026-10-05, lib/site.ts → conciergeNotes),
 * а сайт — по ценам Exely; 2026-11-05 в карточке отеля в Google сайт стоял
 * 26 350 ₸ против 34 806 ₸ у Booking.com. Процент на сайте не пишем: у
 * Booking.com бывают свои скидки, и точная цифра однажды станет неправдой,
 * а «дешевле» остаётся верным, пока работает наценка.
 */
const T = {
  ru: { title: "Дешевле, чем на Booking.com", note: "Бронь на сайте — без наценки площадки" },
  en: { title: "Cheaper than on Booking.com", note: "Book direct — no platform markup" },
} as const;

export function DirectBadge({ lang = "ru", className = "" }: { lang?: Lang; className?: string }) {
  const t = T[lang];
  return (
    <p
      className={`inline-flex items-center gap-2.5 rounded-full border border-sand-400/35 bg-sand-400/10 px-3.5 py-1.5 text-xs text-sand-100 sm:text-[0.8rem] ${className}`}
    >
      <svg viewBox="0 0 24 24" className="size-4 shrink-0 text-sand-300" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <path d="M20 12 12 20l-8-8V4h8z" strokeLinejoin="round" />
        <circle cx="8.5" cy="8.5" r="1.3" fill="currentColor" stroke="none" />
      </svg>
      <span>
        <strong className="font-semibold text-sand-200">{t.title}</strong>
        <span className="hidden text-cream/70 sm:inline"> · {t.note}</span>
      </span>
    </p>
  );
}
