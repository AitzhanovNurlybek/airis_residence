"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { getBookingHref, bookingConfig } from "@/lib/booking";
import { rooms } from "@/lib/site";

const toISO = (d: Date) => d.toISOString().slice(0, 10);
const addDays = (d: Date, n: number) => new Date(d.getTime() + n * 86400000);

/**
 * Строка подбора дат. Не считает цену и не держит наличие —
 * она собирает параметры и передаёт их в getBookingHref().
 * Когда подключат движок брони, эти же параметры уедут в него.
 */
export function BookingBar({ roomSlug, compact = false }: { roomSlug?: string; compact?: boolean }) {
  const router = useRouter();
  const today = new Date();
  const [checkIn, setCheckIn] = useState(toISO(addDays(today, 1)));
  const [checkOut, setCheckOut] = useState(toISO(addDays(today, 2)));
  const [adults, setAdults] = useState(2);
  const [room, setRoom] = useState(roomSlug ?? "");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const href = getBookingHref({ checkIn, checkOut, adults, room: room || undefined });
    if (bookingConfig.mode === "engine") {
      window.open(href, "_blank", "noopener,noreferrer");
    } else {
      router.push(href);
    }
  };

  const field =
    "w-full rounded-xl border border-white/12 bg-ink-900/70 px-3.5 py-3 text-sm text-cream outline-none transition-colors focus:border-sand-400/60 [color-scheme:dark]";
  const label = "mb-1.5 block text-[0.65rem] tracking-[0.16em] text-sand-400 uppercase";

  return (
    <form
      onSubmit={submit}
      className={`glass rounded-3xl p-3 shadow-deep md:p-4 ${compact ? "" : "md:rounded-full"}`}
    >
      {/* На узком экране поля идут парами, а не длинным столбцом */}
      <div
        className={`grid grid-cols-2 gap-3 ${
          compact ? "" : "md:grid-cols-[1fr_1fr_auto_auto] md:items-end md:gap-4 md:px-3"
        }`}
      >
        <div>
          <label className={label} htmlFor="bb-checkin">
            Заезд
          </label>
          <input
            id="bb-checkin"
            type="date"
            className={field}
            value={checkIn}
            min={toISO(today)}
            onChange={(e) => {
              setCheckIn(e.target.value);
              if (e.target.value >= checkOut) setCheckOut(toISO(addDays(new Date(e.target.value), 1)));
            }}
          />
        </div>

        <div>
          <label className={label} htmlFor="bb-checkout">
            Выезд
          </label>
          <input
            id="bb-checkout"
            type="date"
            className={field}
            value={checkOut}
            min={toISO(addDays(new Date(checkIn), 1))}
            onChange={(e) => setCheckOut(e.target.value)}
          />
        </div>

        <div className={compact ? "" : "md:w-32"}>
          <label className={label} htmlFor="bb-adults">
            Гостей
          </label>
          <select
            id="bb-adults"
            className={field}
            value={adults}
            onChange={(e) => setAdults(Number(e.target.value))}
          >
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>

        {compact && !roomSlug && (
          <div>
            <label className={label} htmlFor="bb-room">
              Тип номера
            </label>
            <select
              id="bb-room"
              className={field}
              value={room}
              onChange={(e) => setRoom(e.target.value)}
            >
              <option value="">Любой</option>
              {rooms.map((r) => (
                <option key={r.slug} value={r.slug}>
                  {r.shortName}
                </option>
              ))}
            </select>
          </div>
        )}

        <button
          type="submit"
          className={`col-span-2 h-12 w-full rounded-full bg-linear-to-b from-wine-500 to-wine-700 px-8 text-sm font-medium text-white shadow-[0_10px_30px_-10px_rgba(160,26,84,0.9)] transition-[transform,background-color,box-shadow] duration-200 ease-airis active:scale-[0.97] can-hover:hover:from-wine-400 can-hover:hover:to-wine-600 ${
            compact ? "" : "md:col-span-1 md:w-auto"
          }`}
        >
          Найти номер
        </button>
      </div>
    </form>
  );
}
