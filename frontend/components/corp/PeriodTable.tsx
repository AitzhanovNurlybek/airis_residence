"use client";

import { useState } from "react";

type Row = { key: string; count: number; amount: number };

/**
 * Разбивка по периодам с переключателем месяц/квартал/год.
 *
 * Все три группировки считаются на сервере и приезжают готовыми. Переключение
 * не ходит на сервер: данных немного, а лишний запрос ради смены одной таблицы
 * при базе на другом континенте стоит дороже, чем весь этот компонент.
 */
export function PeriodTable({
  groups,
  labels,
  columns,
  currency,
  empty,
}: {
  groups: { month: Row[]; quarter: Row[]; year: Row[] };
  labels: { month: string; quarter: string; year: string };
  columns: { period: string; count: string; amount: string };
  currency: string;
  empty: string;
}) {
  const [mode, setMode] = useState<"month" | "quarter" | "year">("month");
  const rows = groups[mode];

  const tab = (value: typeof mode, label: string) => (
    <button
      key={value}
      type="button"
      onClick={() => setMode(value)}
      aria-pressed={mode === value}
      className={`rounded-full px-3.5 py-1.5 text-xs transition-colors ${
        mode === value
          ? "bg-wine-500 text-white"
          : "text-ink-700/70 hover:bg-ink-600/8 hover:text-ink-950"
      }`}
    >
      {label}
    </button>
  );

  return (
    <>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        {tab("month", labels.month)}
        {tab("quarter", labels.quarter)}
        {tab("year", labels.year)}
      </div>

      {rows.length === 0 ? (
        <p className="mt-4 rounded-3xl bg-white p-8 text-center text-ink-700/60 shadow-sm">{empty}</p>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-3xl bg-white shadow-sm">
          <table className="w-full min-w-[30rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase">
                <th className="px-5 py-4 font-normal">{columns.period}</th>
                <th className="px-5 py-4 text-right font-normal">{columns.count}</th>
                <th className="px-5 py-4 text-right font-normal">{columns.amount}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-b border-ink-600/8 last:border-0">
                  <td className="px-5 py-4">{row.key}</td>
                  <td className="px-5 py-4 text-right tabular-nums">{row.count}</td>
                  <td className="px-5 py-4 text-right tabular-nums whitespace-nowrap">
                    {new Intl.NumberFormat("ru-RU").format(row.amount).replace(/\s/g, " ")} {currency}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
