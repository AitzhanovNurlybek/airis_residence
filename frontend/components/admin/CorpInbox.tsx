import Link from "next/link";

import { CORP_STATUSES, type AdminCorpBooking } from "@/lib/adminTypes";

/**
 * Заявки компаний, ждущие менеджера — над списком компаний.
 *
 * До этого корпоративную заявку можно было увидеть только внутри карточки
 * конкретной компании: чтобы понять, есть ли новые, пришлось бы открывать
 * компании по очереди. Ровно так на сайте потерялись шесть обращений — их
 * тоже никто не открывал, потому что незачем было заходить.
 *
 * Здесь только то, что требует действия. Оплаченные и отменённые не
 * показываем: список нужен как «что сделать сегодня», а не как архив.
 */

const money = new Intl.NumberFormat("ru-RU");

function daysUntil(checkIn: string): number | null {
  const date = new Date(`${checkIn}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((date.getTime() - today.getTime()) / 86_400_000);
}

function shortDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("ru-RU");
}

export function CorpInbox({ bookings }: { bookings: AdminCorpBooking[] }) {
  const pending = bookings
    .filter((b) => b.status === "new" || b.status === "confirmed" || b.status === "invoiced")
    .sort((a, b) => a.checkIn.localeCompare(b.checkIn));

  if (pending.length === 0) return null;

  const fresh = pending.filter((b) => b.status === "new").length;

  return (
    <section className="mt-8 rounded-3xl border border-sand-400/30 bg-ink-900/60 p-6 md:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-display text-2xl text-cream">Заявки компаний в работе</h2>
        <span className="text-sm text-muted">
          {fresh > 0 ? `новых — ${fresh} из ${pending.length}` : `всего ${pending.length}`}
        </span>
      </div>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
        Всё, что ждёт вашего действия: подтвердить наличие, выставить счёт, отметить
        оплату. Оплаченные и отменённые сюда не попадают.
      </p>

      <div className="mt-5 grid gap-2.5">
        {pending.map((booking) => {
          const status = CORP_STATUSES.find((s) => s.value === booking.status);
          const days = daysUntil(booking.checkIn);
          const burning = days !== null && days <= 3 && booking.status !== "paid";
          return (
            <Link
              key={booking.id}
              href={`/admin/kompanii/${booking.companySlug}`}
              className={`flex flex-wrap items-center justify-between gap-x-5 gap-y-2 rounded-2xl border px-5 py-4 transition-colors ${
                burning
                  ? "border-wine-400/50 bg-wine-900/20 hover:border-wine-400/80"
                  : "border-white/10 bg-ink-950/40 hover:border-sand-400/40"
              }`}
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-cream">{booking.companyName || "—"}</span>
                  {burning && (
                    <span className="rounded-full bg-wine-500 px-2.5 py-0.5 text-[0.65rem] tracking-wide text-white uppercase">
                      {days === 0 ? "заезд сегодня" : days === 1 ? "заезд завтра" : `заезд через ${days} дн.`}
                    </span>
                  )}
                </div>
                <div className="mt-1 text-xs text-muted">
                  {booking.number} · {shortDate(booking.checkIn)} — {shortDate(booking.checkOut)} ·{" "}
                  {booking.items.map((i) => `${i.roomName} × ${i.roomsCount}`).join(", ")}
                  {booking.guestName ? ` · ${booking.guestName}` : ""}
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-4">
                <span className="text-sm text-sand-200 tabular-nums">
                  {money.format(booking.totalAmount)} ₸
                </span>
                <span
                  className={`rounded-full border px-3 py-1 text-xs whitespace-nowrap ${status?.tone ?? "border-white/15 text-muted"}`}
                >
                  {status?.label ?? booking.status}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
