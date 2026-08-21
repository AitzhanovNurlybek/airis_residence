import Link from "next/link";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { formatDate, formatMoney, getDictionary } from "@/lib/corp/dictionary";
import { getCorpBookings, getCorpLocale, getCorpMe } from "@/lib/corp/server";
import type { CorpBooking } from "@/lib/corp/types";

/**
 * Финансы компании.
 *
 * Считается из тех же броней, что показывает история: отдельного эндпоинта нет
 * и не нужно — цифры обязаны сходиться с таблицей до тенге, а два независимых
 * источника рано или поздно разойдутся.
 *
 * В образце заказчика есть ещё колонки «Предоплачено» и «Удержано штрафов».
 * У нас таких сущностей нет: договор постоплатный, штрафы система не считает.
 * Колонка, которая всегда ноль и никогда не заполнится, — это цифра, за
 * которой ничего не стоит; вместо них взяты оплаченное и отменённое.
 */

const sum = (list: CorpBooking[]) => list.reduce((acc, b) => acc + b.totalAmount, 0);

/** Месяц брони считаем по дате заезда: расход ложится на месяц поездки. */
const monthKey = (booking: CorpBooking) => booking.checkIn.slice(0, 7);

export default async function CorpFinancePage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const [me, bookingsResult] = await Promise.all([getCorpMe(), getCorpBookings()]);
  if (!me) redirect("/corp/login");
  // Деньги компании — дело ответственного. Рядовой сотрудник видит только свои
  // брони, и сводка по всей компании ему ничего не скажет, кроме лишнего.
  if (me.user.role !== "admin") redirect("/corp");

  const bookings = bookingsResult ?? [];
  const t = dict.finance;

  const live = bookings.filter((b) => b.status !== "cancelled");
  const paid = bookings.filter((b) => b.status === "paid");
  const cancelled = bookings.filter((b) => b.status === "cancelled");
  const owed = bookings.filter((b) => b.status === "confirmed" || b.status === "invoiced");

  const cards = [
    { label: t.accrued, value: sum(live), accent: false },
    { label: t.paid, value: sum(paid), accent: false },
    { label: t.cancelledSum, value: sum(cancelled), accent: false },
    { label: t.toPay, value: sum(owed), accent: true },
  ];

  const months = new Map<string, { count: number; accrued: number; paid: number; debt: number }>();
  for (const booking of live) {
    const key = monthKey(booking);
    const row = months.get(key) ?? { count: 0, accrued: 0, paid: 0, debt: 0 };
    row.count += 1;
    row.accrued += booking.totalAmount;
    if (booking.status === "paid") row.paid += booking.totalAmount;
    if (booking.status === "confirmed" || booking.status === "invoiced") {
      row.debt += booking.totalAmount;
    }
    months.set(key, row);
  }
  const monthRows = [...months.entries()].sort((a, b) => b[0].localeCompare(a[0]));

  // В таблице показываем всё, за что компания платит, а не только выставленные
  // счета: иначе до первого счёта раздел выглядит пустым, хотя брони уже есть
  // и деньги за них будут.
  const rows = [...live].sort((a, b) => b.checkIn.localeCompare(a.checkIn));

  return (
    <>
      <CorpHeader
        dict={dict}
        locale={locale}
        companyName={me.company.name}
        userName={me.user.fullName || me.user.email}
        isAdmin
      />

      <main className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <Link
          href="/corp"
          prefetch={false}
          className="text-sm text-wine-600 underline underline-offset-4"
        >
          ← {dict.nav.back}
        </Link>

        <h1 className="mt-5 font-display text-[clamp(1.9rem,4vw,2.8rem)] leading-tight font-semibold">
          {t.title}
        </h1>
        <p className="mt-2 text-sm text-ink-700/65">{t.subtitle}</p>

        <section className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((card) => (
            <div
              key={card.label}
              className={`rounded-2xl bg-white px-6 py-5 shadow-sm ${
                card.accent ? "ring-1 ring-wine-500/40" : ""
              }`}
            >
              <div className="text-xs text-ink-700/55">{card.label}</div>
              <div
                className={`mt-2 font-display text-2xl leading-none font-semibold ${
                  card.accent ? "text-wine-500" : "text-ink-950"
                }`}
              >
                {formatMoney(card.value)} {dict.common.currency}
              </div>
            </div>
          ))}
        </section>

        {me.company.paymentTerms && (
          <p className="mt-4 text-xs text-ink-700/60">
            {t.terms}: {me.company.paymentTerms}
          </p>
        )}

        <h2 className="mt-10 font-display text-2xl">{t.byMonth}</h2>
        {monthRows.length === 0 ? (
          <p className="mt-4 rounded-3xl bg-white p-8 text-center text-ink-700/60 shadow-sm">
            {t.noMonths}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-3xl bg-white shadow-sm">
            <table className="w-full min-w-[38rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase">
                  <th className="px-5 py-4 font-normal">{t.month}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.monthBookings}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.accrued}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.paid}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.toPay}</th>
                </tr>
              </thead>
              <tbody>
                {monthRows.map(([key, row]) => (
                  <tr key={key} className="border-b border-ink-600/8 last:border-0">
                    <td className="px-5 py-4 whitespace-nowrap">{key}</td>
                    <td className="px-5 py-4 text-right tabular-nums">{row.count}</td>
                    <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(row.accrued)}
                    </td>
                    <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                      {row.paid ? formatMoney(row.paid) : "—"}
                    </td>
                    <td className="px-5 py-4 text-right font-medium tabular-nums whitespace-nowrap text-wine-500">
                      {row.debt ? formatMoney(row.debt) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h2 className="mt-10 font-display text-2xl">{t.invoices}</h2>
        {rows.length === 0 ? (
          <p className="mt-4 rounded-3xl bg-white p-8 text-center text-ink-700/60 shadow-sm">
            {t.noInvoices}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-3xl bg-white shadow-sm">
            <table className="w-full min-w-[44rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase">
                  <th className="px-5 py-4 font-normal">{t.invoiceOrBooking}</th>
                  <th className="px-5 py-4 font-normal">{t.issued}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.accrued}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.toPay}</th>
                  <th className="px-5 py-4 font-normal">{dict.bookings.status}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((booking) => {
                  const unpaid = booking.status === "confirmed" || booking.status === "invoiced";
                  return (
                    <tr key={booking.id} className="border-b border-ink-600/8 last:border-0">
                      <td className="px-5 py-4">
                        {booking.invoiceNumber ? (
                          <span className="text-ink-950">
                            {t.invoiceNumber} {booking.invoiceNumber}
                          </span>
                        ) : (
                          <span className="text-ink-700/70">{booking.number}</span>
                        )}
                        <span className="mt-0.5 block text-xs text-ink-700/50">
                          {formatDate(booking.checkIn, locale)} —{" "}
                          {formatDate(booking.checkOut, locale)}
                        </span>
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap text-ink-700/80">
                        {formatDate(booking.createdAt, locale)}
                      </td>
                      <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                        {formatMoney(booking.totalAmount)}
                      </td>
                      <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                        {unpaid ? (
                          <span className="text-wine-500">{formatMoney(booking.totalAmount)}</span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <span className="inline-block rounded-full bg-sand-200/70 px-3 py-1 text-xs whitespace-nowrap text-ink-800">
                          {dict.status[booking.status]}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-6 text-xs leading-relaxed text-ink-700/55">{t.footnote}</p>
      </main>
    </>
  );
}
