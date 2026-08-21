import Link from "next/link";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { PeriodTable } from "@/components/corp/PeriodTable";
import { formatMoney, getDictionary } from "@/lib/corp/dictionary";
import { getCorpBookings, getCorpLocale, getCorpMe } from "@/lib/corp/server";
import { isActiveBooking, type CorpBooking } from "@/lib/corp/types";

/**
 * Отчёты компании: по периодам, по сотрудникам и по статусам.
 *
 * Считается из тех же броней, что и всё остальное в кабинете. Разбивки
 * группируются на сервере сразу все три — данных немного, а лишний запрос при
 * базе на другом континенте стоит дороже, чем посчитать их разом.
 */

/** Период брони берём по дате заезда: расход относится к месяцу поездки. */
function periodKeys(booking: CorpBooking) {
  const [year, month] = booking.checkIn.split("-");
  const quarter = Math.floor((Number(month) - 1) / 3) + 1;
  return { month: `${year}-${month}`, quarter: `${year} · Q${quarter}`, year };
}

type Row = { key: string; count: number; amount: number };

function group(bookings: CorpBooking[], keyOf: (b: CorpBooking) => string): Row[] {
  const map = new Map<string, Row>();
  for (const booking of bookings) {
    const key = keyOf(booking);
    const row = map.get(key) ?? { key, count: 0, amount: 0 };
    row.count += 1;
    row.amount += booking.totalAmount;
    map.set(key, row);
  }
  return [...map.values()].sort((a, b) => b.key.localeCompare(a.key));
}

export default async function CorpReportsPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const [me, bookingsResult] = await Promise.all([getCorpMe(), getCorpBookings()]);
  if (!me) redirect("/corp/login");
  if (me.user.role !== "admin") redirect("/corp");

  const all = bookingsResult ?? [];
  // Отменённые не считаются: за них компания не платит, а в отчёте они
  // раздували бы сумму и делали его бесполезным для сверки с бухгалтерией.
  const bookings = all.filter((b) => b.status !== "cancelled");
  const t = dict.reports;

  const cards = [
    { value: String(all.filter(isActiveBooking).length), label: t.activeLabel, accent: false },
    {
      value: formatMoney(bookings.reduce((s, b) => s + b.totalAmount, 0)),
      label: t.sumLabel,
      accent: true,
    },
    {
      value: formatMoney(
        all.filter((b) => b.status === "paid").reduce((s, b) => s + b.totalAmount, 0),
      ),
      label: t.paidLabel,
      accent: false,
    },
    {
      value: formatMoney(
        all.filter((b) => b.status === "cancelled").reduce((s, b) => s + b.totalAmount, 0),
      ),
      label: t.cancelledLabel,
      accent: false,
    },
  ];

  const groups = {
    month: group(bookings, (b) => periodKeys(b).month),
    quarter: group(bookings, (b) => periodKeys(b).quarter),
    year: group(bookings, (b) => periodKeys(b).year),
  };

  const byEmployee = new Map<string, { count: number; nights: number; amount: number }>();
  for (const booking of bookings) {
    const key = booking.createdByName || "—";
    const row = byEmployee.get(key) ?? { count: 0, nights: 0, amount: 0 };
    row.count += 1;
    row.nights += booking.nights;
    row.amount += booking.totalAmount;
    byEmployee.set(key, row);
  }
  const employeeRows = [...byEmployee.entries()].sort((a, b) => b[1].amount - a[1].amount);
  const total = employeeRows.reduce(
    (acc, [, row]) => ({
      count: acc.count + row.count,
      nights: acc.nights + row.nights,
      amount: acc.amount + row.amount,
    }),
    { count: 0, nights: 0, amount: 0 },
  );

  // По статусам считаем все брони, включая отменённые: смысл этой таблицы
  // как раз в том, чтобы видеть, сколько заявок отвалилось и на какую сумму.
  const statusRows = group(all, (b) => b.status).sort((a, b) => b.amount - a.amount);

  const th = "px-5 py-4 font-normal";
  const headRow = "border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase";

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
            <div key={card.label} className="rounded-2xl bg-white px-6 py-5 shadow-sm">
              <div
                className={`font-display text-3xl leading-none font-semibold ${
                  card.accent ? "text-wine-500" : "text-ink-950"
                }`}
              >
                {card.value}
              </div>
              <div className="mt-2 text-xs text-ink-700/60">{card.label}</div>
            </div>
          ))}
        </section>

        <h2 className="mt-10 font-display text-2xl">{t.byPeriod}</h2>
        <PeriodTable
          groups={groups}
          labels={{ month: t.periodMonth, quarter: t.periodQuarter, year: t.periodYear }}
          columns={{ period: t.period, count: t.bookingsCount, amount: t.amount }}
          currency={dict.common.currency}
          empty={t.empty}
        />

        <h2 className="mt-10 font-display text-2xl">{t.employee}</h2>
        {employeeRows.length === 0 ? (
          <p className="mt-4 rounded-3xl bg-white p-8 text-center text-ink-700/60 shadow-sm">
            {t.empty}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-3xl bg-white shadow-sm">
            <table className="w-full min-w-[36rem] border-collapse text-sm">
              <thead>
                <tr className={headRow}>
                  <th className={th}>{t.employee}</th>
                  <th className={`${th} text-right`}>{t.bookingsCount}</th>
                  <th className={`${th} text-right`}>{t.nights}</th>
                  <th className={`${th} text-right`}>{t.amount}</th>
                </tr>
              </thead>
              <tbody>
                {employeeRows.map(([name, row]) => (
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

        <h2 className="mt-10 font-display text-2xl">{t.byStatus}</h2>
        {statusRows.length === 0 ? (
          <p className="mt-4 rounded-3xl bg-white p-8 text-center text-ink-700/60 shadow-sm">
            {t.empty}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-3xl bg-white shadow-sm">
            <table className="w-full min-w-[30rem] border-collapse text-sm">
              <thead>
                <tr className={headRow}>
                  <th className={th}>{t.statusLabel}</th>
                  <th className={`${th} text-right`}>{t.count}</th>
                  <th className={`${th} text-right`}>{t.amount}</th>
                </tr>
              </thead>
              <tbody>
                {statusRows.map((row) => (
                  <tr key={row.key} className="border-b border-ink-600/8 last:border-0">
                    <td className="px-5 py-4">
                      {dict.status[row.key as keyof typeof dict.status] ?? row.key}
                    </td>
                    <td className="px-5 py-4 text-right tabular-nums">{row.count}</td>
                    <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                      {formatMoney(row.amount)} {dict.common.currency}
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
