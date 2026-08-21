import Link from "next/link";
import { redirect } from "next/navigation";

import { CancelBooking } from "@/components/corp/CancelBooking";
import { CorpHeader } from "@/components/corp/CorpHeader";
import {
  formatDate,
  formatMoney,
  formatNights,
  getDictionary,
} from "@/lib/corp/dictionary";
import { getCorpBookings, getCorpLocale, getCorpMe } from "@/lib/corp/server";
import { isActiveBooking, type BookingStatus } from "@/lib/corp/types";

/** Цвет плашки статуса. Оплачено — зелёное, отменено — приглушённое. */
const STATUS_STYLE: Record<BookingStatus, string> = {
  new: "bg-sand-200 text-ink-800",
  confirmed: "bg-sand-300/60 text-ink-900",
  invoiced: "bg-wine-50 text-wine-600",
  paid: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-ink-600/10 text-ink-700/60",
};

export default async function CorpBookingsPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const me = await getCorpMe();
  if (!me) redirect("/corp/login");

  const bookings = (await getCorpBookings()) ?? [];

  return (
    <>
      <CorpHeader
        dict={dict}
        locale={locale}
        companyName={me.company.name}
        userName={me.user.fullName || me.user.email}
      />

      <main className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <Link
          href="/corp"
          className="text-sm text-wine-600 underline underline-offset-4"
        >
          ← {dict.nav.back}
        </Link>

        <h1 className="mt-5 font-display text-[clamp(1.9rem,4vw,2.8rem)] leading-tight font-semibold">
          {dict.bookings.title}
        </h1>

        {bookings.length === 0 ? (
          <div className="mt-8 rounded-3xl bg-white p-10 text-center shadow-sm">
            <p className="text-lg text-ink-950">{dict.bookings.empty}</p>
            <p className="mt-2 text-sm text-ink-700/60">{dict.bookings.emptyHint}</p>
          </div>
        ) : (
          /* Таблица шире телефона и обязана прокручиваться внутри себя:
             горизонтальный скролл всей страницы ломает вёрстку целиком. */
          <div className="mt-8 overflow-x-auto rounded-3xl bg-white shadow-sm">
            <table className="w-full min-w-[52rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase">
                  <th className="px-5 py-4 font-normal">{dict.bookings.number}</th>
                  <th className="px-5 py-4 font-normal">{dict.bookings.dates}</th>
                  <th className="px-5 py-4 font-normal">{dict.bookings.category}</th>
                  <th className="px-5 py-4 text-right font-normal">{dict.bookings.rooms}</th>
                  <th className="px-5 py-4 text-right font-normal">{dict.bookings.amount}</th>
                  <th className="px-5 py-4 font-normal">{dict.bookings.status}</th>
                  <th className="px-5 py-4 font-normal">{dict.bookings.employee}</th>
                  <th className="px-5 py-4" />
                </tr>
              </thead>
              <tbody>
                {bookings.map((booking) => (
                  <tr key={booking.id} className="border-b border-ink-600/8 last:border-0">
                    <td className="px-5 py-4 whitespace-nowrap">{booking.number}</td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      {formatDate(booking.checkIn, locale)} — {formatDate(booking.checkOut, locale)}
                      <span className="mt-0.5 block text-xs text-ink-700/50">
                        {formatNights(booking.nights, dict, locale)}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      {booking.items.map((item) => item.roomName).join(", ") || "—"}
                    </td>
                    <td className="px-5 py-4 text-right">
                      {booking.items.reduce((sum, item) => sum + item.roomsCount, 0)}
                    </td>
                    <td className="px-5 py-4 text-right whitespace-nowrap">
                      {formatMoney(booking.totalAmount)}
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-block rounded-full px-3 py-1 text-xs whitespace-nowrap ${STATUS_STYLE[booking.status]}`}
                      >
                        {dict.status[booking.status]}
                      </span>
                      {booking.invoiceNumber && (
                        <span className="mt-1 block text-xs text-ink-700/50">
                          {dict.bookings.invoice} {booking.invoiceNumber}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-ink-700/70">{booking.createdByName || "—"}</td>
                    <td className="px-5 py-4 text-right">
                      {isActiveBooking(booking) && (
                        <CancelBooking
                          bookingId={booking.id}
                          label={dict.bookings.cancel}
                          confirmText={`${dict.bookings.title}: ${booking.number}?`}
                        />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </>
  );
}
