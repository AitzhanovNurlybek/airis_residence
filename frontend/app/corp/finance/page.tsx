import Link from "next/link";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { formatDate, formatMoney, getDictionary } from "@/lib/corp/dictionary";
import { getCorpBookings, getCorpLocale, getCorpMe } from "@/lib/corp/server";

/**
 * Финансы компании.
 *
 * Считается из тех же броней, что показывает история: отдельного эндпоинта нет
 * и не нужно — цифры должны сходиться с таблицей до тенге, а два независимых
 * источника рано или поздно разойдутся.
 */
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

  const sum = (list: typeof bookings) => list.reduce((acc, b) => acc + b.totalAmount, 0);
  const awaitingConfirm = bookings.filter((b) => b.status === "new");
  const invoiced = bookings.filter((b) => b.status === "invoiced");
  const confirmed = bookings.filter((b) => b.status === "confirmed");
  const paid = bookings.filter((b) => b.status === "paid");
  const debt = [...confirmed, ...invoiced];

  const withInvoice = bookings
    .filter((b) => b.invoiceNumber)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  const cards = [
    { label: t.awaitingConfirm, value: formatMoney(sum(awaitingConfirm)), note: `${awaitingConfirm.length}` },
    { label: t.awaitingPayment, value: formatMoney(sum(invoiced)), note: `${invoiced.length}` },
    { label: t.paid, value: formatMoney(sum(paid)), note: `${paid.length}` },
  ];

  return (
    <>
      <CorpHeader
        dict={dict}
        locale={locale}
        companyName={me.company.name}
        userName={me.user.fullName || me.user.email}
      />

      <main className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <Link href="/corp" prefetch={false} className="text-sm text-wine-600 underline underline-offset-4">
          ← {dict.nav.back}
        </Link>

        <h1 className="mt-5 font-display text-[clamp(1.9rem,4vw,2.8rem)] leading-tight font-semibold">
          {t.title}
        </h1>
        <p className="mt-2 text-sm text-ink-700/65">{t.subtitle}</p>

        <section className="mt-8 grid gap-4 sm:grid-cols-3">
          {cards.map((card) => (
            <div key={card.label} className="rounded-2xl bg-white px-6 py-5 shadow-sm">
              <div className="font-display text-2xl leading-none font-semibold text-wine-500">
                {card.value} {dict.common.currency}
              </div>
              <div className="mt-2 text-xs text-ink-700/60">
                {card.label} · {card.note}
              </div>
            </div>
          ))}
        </section>

        <section className="mt-4 rounded-2xl border-l-2 border-wine-500 bg-white px-6 py-5 shadow-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <span className="text-sm text-ink-700/70">{t.debt}</span>
            <span className="font-display text-3xl font-semibold text-wine-500">
              {formatMoney(sum(debt))} {dict.common.currency}
            </span>
          </div>
          <p className="mt-2 text-xs text-ink-700/55">{t.debtHint}</p>
          {me.company.paymentTerms && (
            <p className="mt-3 border-t border-ink-600/10 pt-3 text-xs text-ink-700/60">
              {t.terms}: {me.company.paymentTerms}
            </p>
          )}
        </section>

        <h2 className="mt-10 font-display text-2xl">{t.invoices}</h2>
        {withInvoice.length === 0 ? (
          <p className="mt-4 rounded-3xl bg-white p-8 text-center text-ink-700/60 shadow-sm">
            {t.noInvoices}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-3xl bg-white shadow-sm">
            <table className="w-full min-w-[40rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase">
                  <th className="px-5 py-4 font-normal">{t.invoiceNumber}</th>
                  <th className="px-5 py-4 font-normal">{t.booking}</th>
                  <th className="px-5 py-4 font-normal">{dict.bookings.dates}</th>
                  <th className="px-5 py-4 text-right font-normal">{dict.bookings.amount}</th>
                  <th className="px-5 py-4 font-normal">{dict.bookings.status}</th>
                </tr>
              </thead>
              <tbody>
                {withInvoice.map((booking) => (
                  <tr key={booking.id} className="border-b border-ink-600/8 last:border-0">
                    <td className="px-5 py-4 whitespace-nowrap">{booking.invoiceNumber}</td>
                    <td className="px-5 py-4 text-ink-700/80">{booking.number}</td>
                    <td className="px-5 py-4 whitespace-nowrap text-ink-700/80">
                      {formatDate(booking.checkIn, locale)} — {formatDate(booking.checkOut, locale)}
                    </td>
                    <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(booking.totalAmount)}
                    </td>
                    <td className="px-5 py-4 text-ink-700/80">{dict.status[booking.status]}</td>
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
