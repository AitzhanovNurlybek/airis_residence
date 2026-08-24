"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminButton } from "@/components/admin/ui";
import { adminGet } from "@/lib/adminClient";
import { hotelToday } from "@/lib/almaty";

/**
 * Настоящее наличие из Exely.
 *
 * Стоит рядом с учебной шахматкой намеренно: так сразу видно, где выдуманные
 * числа, а где настоящие. Учебная нужна, чтобы проверять запись — оформление,
 * перенос, отмену. Эта показывает правду, но только на чтение.
 *
 * Данные идут с того же адреса, куда ходит форма брони на страницах сайта.
 * Адрес недокументированный: он может измениться в любой день, поэтому сбой
 * здесь ничего не ломает — блок просто честно говорит, что не дозвонился.
 */

type Offer = { roomSlug: string; roomName: string; roomsLeft: number | null };
type Result = { checkIn: string; checkOut: string; nights: number; offers: Offer[] };

function addDays(iso: string, count: number): string {
  const base = new Date(`${iso}T12:00:00`);
  base.setDate(base.getDate() + count);
  return base.toISOString().slice(0, 10);
}

export function ExelyAvailability() {
  const [from, setFrom] = useState(addDays(hotelToday(), 1));
  const [to, setTo] = useState(addDays(hotelToday(), 3));
  const [data, setData] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const ask = useCallback(async (a: string, b: string) => {
    setBusy(true);
    setError("");
    try {
      setData(await adminGet<Result>(`/local/exely?check_in=${a}&check_out=${b}`));
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "Exely не ответил");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void ask(from, to);
    // Только при первом показе: дальше даты меняет человек кнопкой, и дёргать
    // чужую систему на каждое нажатие стрелки в поле даты незачем.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const total = data?.offers.reduce((sum, o) => sum + (o.roomsLeft ?? 0), 0) ?? 0;

  return (
    <div className="rounded-2xl border border-white/10 bg-ink-900/50 p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 className="font-display text-xl text-cream">Настоящее наличие из Exely</h3>
          <p className="mt-1 text-sm text-muted">
            То же, что видит гость в форме брони. Только чтение.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="date"
            value={from}
            onChange={(e) => {
              const v = e.target.value || hotelToday();
              setFrom(v);
              if (to <= v) setTo(addDays(v, 1));
            }}
            className="h-9 rounded-xl border border-white/12 bg-ink-950/60 px-3 text-sm text-cream"
          />
          <span className="text-muted">—</span>
          <input
            type="date"
            min={addDays(from, 1)}
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="h-9 rounded-xl border border-white/12 bg-ink-950/60 px-3 text-sm text-cream"
          />
          <AdminButton
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => void ask(from, to)}
          >
            {busy ? "Спрашиваю…" : "Спросить Exely"}
          </AdminButton>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-xl bg-wine-600/15 px-4 py-3 text-sm text-wine-200">
          {error}. Наличие в этот момент лучше уточнить на стойке.
        </p>
      )}

      {data && (
        <>
          <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {data.offers.map((o) => {
              const left = o.roomsLeft ?? 0;
              return (
                <div
                  key={o.roomSlug}
                  className={`flex items-center justify-between rounded-xl border px-4 py-3 ${
                    left > 0
                      ? "border-white/10 bg-ink-950/40"
                      : "border-wine-400/30 bg-wine-600/10"
                  }`}
                >
                  <span className="text-sm text-cream">{o.roomName}</span>
                  <span
                    className={`text-sm tabular-nums ${left > 0 ? "text-sand-200" : "text-wine-300"}`}
                  >
                    {left > 0 ? `свободно ${left}` : "нет"}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-muted">
            {data.nights} ноч., всего свободных номеров: {total}. Данные приходят с того же
            адреса, куда обращается форма брони на сайте. Оформить бронь отсюда нельзя — для
            записи нужен договорной доступ к API, его ещё предстоит получить у интеграторов.
          </p>
        </>
      )}
    </div>
  );
}
