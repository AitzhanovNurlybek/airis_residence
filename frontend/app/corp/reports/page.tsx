import Link from "next/link";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { formatMoney, getDictionary } from "@/lib/corp/dictionary";
import { getCorpBookings, getCorpLocale, getCorpMe } from "@/lib/corp/server";

/**
 * Расходы по сотрудникам.
 *
 * Отменённые заявки не считаются: за них компания не платит, а в отчёте они
 * раздували бы сумму и делали его бесполезным для сверки с бухгалтерией.
 */
export default async function CorpReportsPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const [me, bookingsResult] = await Promise.all([getCorpMe(), getCorpBookings()]);
  if (!me) redirect("/corp/login");
  if (me.user.role !== "admin") redirect("/corp");

  const bookings = (bookingsResult ?? []).filter((b) => b.status !== "cancelled");
  const t = dict.reports;

  const byEmployee = new Map<string, { count: number; nights: number; amount: number }>();
  for (const booking of bookings) {
    const key = booking.createdByName || "—";
    const row = byEmployee.get(key) ?? { count: 0, nights: 0, amount: 0 };
    row.count += 1;
    row.nights += booking.nights;
    row.amount += booking.totalAmount;
    byEmployee.set(key, row);
  }
  const rows = [...byEmployee.entries()].sort((a, b) => b[1].amount - a[1].amount);
  const total = rows.reduce(
    (acc, [, row]) => ({
      count: acc.count + row.count,
      nights: acc.nights + row.nights,
      amount: acc.amount + row.amount,
    }),
    { count: 0, nights: 0, amount: 0 },
  );

  return (
    <>
      <CorpHeader
        dict={dict}
        locale={locale}
        companyName={me.company.name}
        userName={me.user.fullName || me.user.email}
        isAdmin={me.user.role === "admin"}
      />

      <main className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <Link href="/corp" prefetch={false} className="text-sm text-wine-600 underline underline-offset-4">
          ← {dict.nav.back}
        </Link>

        <h1 className="mt-5 font-display text-[clamp(1.9rem,4vw,2.8rem)] leading-tight font-semibold">
          {t.title}
        </h1>
        <p className="mt-2 text-sm text-ink-700/65">{t.subtitle}</p>

        {rows.length === 0 ? (
          <p className="mt-8 rounded-3xl bg-white p-10 text-center text-ink-700/60 shadow-sm">
            {t.empty}
          </p>
        ) : (
          <div className="mt-8 overflow-x-auto rounded-3xl bg-white shadow-sm">
            <table className="w-full min-w-[36rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase">
                  <th className="px-5 py-4 font-normal">{t.employee}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.bookingsCount}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.nights}</th>
                  <th className="px-5 py-4 text-right font-normal">{t.amount}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([name, row]) => (
                  <tr key={name} className="border-b border-ink-600/8">
                    <td className="px-5 py-4">{name}</td>
                    <td className="px-5 py-4 text-right tabular-nums">{row.count}</td>
                    <td className="px-5 py-4 text-right tabular-nums">{row.nights}</td>
                    <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(row.amount)} {dict.common.currency}
                    </td>
                  </tr>
                ))}
                <tr className="bg-sand-100/60">
                  <td className="px-5 py-4 font-medium">{t.total}</td>
                  <td className="px-5 py-4 text-right tabular-nums">{total.count}</td>
                  <td className="px-5 py-4 text-right tabular-nums">{total.nights}</td>
                  <td className="px-5 py-4 text-right font-medium tabular-nums whitespace-nowrap text-wine-500">
                    {formatMoney(total.amount)} {dict.common.currency}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </main>
    </>
  );
}
