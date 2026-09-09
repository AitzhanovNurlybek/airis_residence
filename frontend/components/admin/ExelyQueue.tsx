"use client";

import { useState } from "react";

import { AdminError, adminSend } from "@/lib/adminClient";
import type { AdminCorpBooking } from "@/lib/adminTypes";

/**
 * Очередь «занести в Exely» — единственная ручная работа, оставшаяся у отеля.
 *
 * Всё остальное в корпоративной брони делается само: доверенному партнёру
 * заявка подтверждается по живому наличию, отель получает уведомление,
 * цены считаются по договору. Занесение автоматизировать нельзя — Exely не
 * создаёт брони извне, только отдаёт наличие.
 *
 * Раз этот шаг остаётся человеку, он должен занимать минимум движений:
 * открыть один экран, скопировать готовый блок, вставить в Exely, нажать
 * «Занесено». Ни поиска по разделам, ни переписывания данных глазами —
 * там, где собирают глазами, путают даты и фамилии.
 *
 * Экран стоит выше общего списка заявок и исчезает, когда очередь пуста:
 * пустой блок «ничего не нужно делать» приучает пролистывать это место.
 */

function waitedFor(confirmedAt: string | null): string {
  if (!confirmedAt) return "";
  const minutes = Math.floor((Date.now() - new Date(confirmedAt).getTime()) / 60000);
  if (Number.isNaN(minutes) || minutes < 1) return "только что";
  if (minutes < 60) return `${minutes} мин. назад`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ч. назад`;
  return `${Math.floor(hours / 24)} дн. назад`;
}

export function ExelyQueue({ bookings }: { bookings: AdminCorpBooking[] }) {
  const [rows, setRows] = useState(bookings);
  const [busy, setBusy] = useState<number | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [error, setError] = useState("");

  const queue = rows
    .filter(
      (b) =>
        b.autoConfirmed &&
        !b.enteredAt &&
        (b.status === "confirmed" || b.status === "invoiced"),
    )
    .sort((a, b) => (a.confirmedAt ?? "").localeCompare(b.confirmedAt ?? ""));

  if (queue.length === 0) return null;

  async function copy(booking: AdminCorpBooking) {
    try {
      await navigator.clipboard.writeText(booking.exelyBlock);
      setCopied(booking.id);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      // Буфер может быть недоступен — например, без HTTPS. Текст и так виден
      // на экране, выделить его руками можно, поэтому это не ошибка.
      setError("Скопировать не вышло — выделите текст вручную");
    }
  }

  async function markEntered(booking: AdminCorpBooking) {
    setBusy(booking.id);
    setError("");
    try {
      const saved = await adminSend<AdminCorpBooking>(
        `/corp/bookings/${booking.id}/entered`,
        "POST",
        { entered: true },
      );
      setRows((prev) => prev.map((b) => (b.id === booking.id ? saved : b)));
    } catch (e) {
      setError(e instanceof AdminError ? e.message : "Не удалось отметить");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mt-8 rounded-3xl border border-amber-500/40 bg-amber-950/20 p-6 md:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-display text-2xl text-cream">Занести в Exely</h2>
        <span className="text-sm text-amber-200/80">{queue.length} в очереди</span>
      </div>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-amber-100/70">
        Партнёрам уже подтверждено, а в шахматке этих броней нет — сама она туда не
        попадёт. Пока не занесены, номер выглядит свободным и его могут продать
        второй раз.
      </p>

      {error && <p className="mt-3 text-sm text-wine-300">{error}</p>}

      <div className="mt-5 grid gap-3">
        {queue.map((booking) => (
          <div
            key={booking.id}
            className="rounded-2xl border border-amber-500/25 bg-ink-950/50 p-4"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-cream">
                {booking.companyName || "—"}{" "}
                <span className="text-xs text-muted">{booking.number}</span>
              </span>
              <span className="text-xs text-amber-200/70">
                подтверждено {waitedFor(booking.confirmedAt)}
              </span>
            </div>

            {/* Готовый блок собран на сервере — тот же, что уходит в WhatsApp.
                Расходись они, человек начал бы сверять два источника вместо
                того, чтобы копировать. */}
            <pre className="mt-3 overflow-x-auto rounded-xl bg-black/40 p-3 text-xs leading-relaxed whitespace-pre-wrap text-cream/90">
              {booking.exelyBlock}
            </pre>

            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => copy(booking)}
                className="rounded-full border border-white/20 px-4 py-1.5 text-sm text-cream transition-colors hover:border-sand-400/60"
              >
                {copied === booking.id ? "Скопировано" : "Скопировать"}
              </button>
              <button
                type="button"
                disabled={busy === booking.id}
                onClick={() => markEntered(booking)}
                className="rounded-full bg-amber-500 px-4 py-1.5 text-sm text-black transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {busy === booking.id ? "…" : "Занесено"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
