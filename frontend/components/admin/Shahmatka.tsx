"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AdminButton } from "@/components/admin/ui";
import { adminGet, adminSend } from "@/lib/adminClient";
import { hotelToday } from "@/lib/almaty";

/**
 * Локальная шахматка: кто где живёт и что свободно.
 *
 * Нужна, пока настоящей шахматки у нас нет. Здесь видно ту самую базу, с
 * которой разговаривает ИИ-консьерж: поставили бронь руками — он тут же
 * начнёт говорить, что номер занят.
 *
 * Календарь нарисован на две недели вперёд. Не потому, что дальше не бывает
 * броней, а потому, что шире экрана таблица становится нечитаемой, а задача
 * страницы — проверить поведение, а не заменить настоящую систему.
 */

type Stock = { roomSlug: string; roomName: string; roomsTotal: number };
type Booking = {
  ref: string;
  room: string;
  roomSlug: string;
  rooms: number;
  checkIn: string;
  checkOut: string;
  guest: string;
  phone: string;
  status: string;
  amount: number;
  paid: number;
  origin: string;
  note: string;
};
type Payment = {
  bookingRef: string;
  docNumber: string;
  amount: number;
  payer: string;
  createdAt: string;
};
type Board = { system: string; stock: Stock[]; bookings: Booking[]; payments: Payment[] };

const DAYS = 14;

function addDays(iso: string, count: number): string {
  const base = new Date(`${iso}T12:00:00`);
  base.setDate(base.getDate() + count);
  return base.toISOString().slice(0, 10);
}

function short(iso: string): string {
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}`;
}

const money = new Intl.NumberFormat("ru-RU");

const input =
  "h-10 w-full rounded-xl border border-white/12 bg-ink-950/60 px-3 text-sm text-cream outline-none focus:border-sand-400/60";

export function Shahmatka({ initial }: { initial: Board | null }) {
  const [board, setBoard] = useState<Board | null>(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [from, setFrom] = useState(hotelToday());

  const [form, setForm] = useState({
    roomSlug: "",
    roomsCount: 1,
    checkIn: hotelToday(),
    checkOut: addDays(hotelToday(), 1),
    guestName: "",
    guestPhone: "",
    amount: 0,
  });

  useEffect(() => {
    if (!form.roomSlug && board?.stock.length) {
      setForm((f) => ({ ...f, roomSlug: board.stock[0].roomSlug }));
    }
  }, [board, form.roomSlug]);

  const reload = useCallback(async () => {
    try {
      const fresh = await adminGet<Board>("/local/board");
      setBoard(fresh);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось обновить");
    }
  }, []);

  const days = useMemo(
    () => Array.from({ length: DAYS }, (_, i) => addDays(from, i)),
    [from],
  );

  // Занятость по клеткам. Считается на клиенте из тех же данных, что уже
  // пришли: отдельный запрос за каждой ночью превратил бы страницу в сотню
  // обращений к серверу ради таблицы, которая целиком лежит в памяти.
  const grid = useMemo(() => {
    const map = new Map<string, number>();
    if (!board) return map;
    for (const b of board.bookings) {
      if (b.status !== "booked") continue;
      for (const day of days) {
        if (day >= b.checkIn && day < b.checkOut) {
          const key = `${b.roomSlug}|${day}`;
          map.set(key, (map.get(key) ?? 0) + b.rooms);
        }
      }
    }
    return map;
  }, [board, days]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await adminSend("/local/bookings", "POST", {
        roomSlug: form.roomSlug,
        roomsCount: Number(form.roomsCount) || 1,
        checkIn: form.checkIn,
        checkOut: form.checkOut,
        guestName: form.guestName.trim(),
        guestPhone: form.guestPhone.trim(),
        amount: Number(form.amount) || 0,
      });
      setForm((f) => ({ ...f, guestName: "", guestPhone: "" }));
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось поставить бронь");
    } finally {
      setBusy(false);
    }
  }

  async function setStock(roomSlug: string, roomsTotal: number) {
    if (!Number.isFinite(roomsTotal) || roomsTotal < 0) return;
    setBusy(true);
    setError("");
    try {
      await adminSend("/local/stock", "PATCH", { roomSlug, roomsTotal });
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось изменить число номеров");
    } finally {
      setBusy(false);
    }
  }

  async function act(ref: string, what: "cancel" | "delete") {
    setBusy(true);
    setError("");
    try {
      if (what === "cancel") await adminSend(`/local/bookings/${ref}/cancel`, "POST", {});
      else await adminSend(`/local/bookings/${ref}`, "DELETE");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не получилось");
    } finally {
      setBusy(false);
    }
  }

  if (!board) {
    return (
      <div className="rounded-2xl border border-white/10 bg-ink-900/50 p-6 text-sm text-muted">
        Локальная шахматка выключена. В <span className="text-cream">backend/.env</span> нужна
        строка <span className="text-sand-300">BOOKING_SYSTEM=local</span>, затем перезапустить
        бэкенд.
      </div>
    );
  }

  const active = board.bookings.filter((b) => b.status === "booked");

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          {board.system} · действующих броней: {active.length}
        </p>
        <div className="flex items-center gap-3">
          <label className="text-xs text-muted">с даты</label>
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value || hotelToday())}
            className="h-9 rounded-xl border border-white/12 bg-ink-950/60 px-3 text-sm text-cream"
          />
          <AdminButton type="button" variant="secondary" onClick={reload} disabled={busy}>
            Обновить
          </AdminButton>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-xl bg-wine-600/15 px-4 py-3 text-sm text-wine-200">
          {error}
        </p>
      )}

      {/* ─────────────── Календарь ─────────────── */}
      <div className="mt-6 overflow-x-auto rounded-2xl border border-white/10 bg-ink-900/50">
        <table className="w-full min-w-[820px] border-collapse text-sm">
          <thead>
            <tr className="text-xs text-muted">
              <th className="sticky left-0 bg-ink-900 px-4 py-3 text-left font-normal">Категория</th>
              {days.map((day) => (
                <th key={day} className="px-2 py-3 text-center font-normal whitespace-nowrap">
                  {short(day)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {board.stock.map((row) => (
              <tr key={row.roomSlug} className="border-t border-white/6">
                <td className="sticky left-0 bg-ink-900 px-4 py-3 whitespace-nowrap text-cream">
                  {row.roomName}
                  {/* Числа взяты с настоящей шахматки, но две категории на
                      снимке было не видно — там оценка. Пусть владелец
                      поправит на месте, а не просит об этом разработчика. */}
                  <label className="ml-3 inline-flex items-center gap-1.5 text-xs text-muted">
                    всего
                    <input
                      type="number"
                      min={0}
                      max={200}
                      defaultValue={row.roomsTotal}
                      disabled={busy}
                      onBlur={(e) => {
                        const next = Number(e.target.value);
                        if (next !== row.roomsTotal) void setStock(row.roomSlug, next);
                      }}
                      className="h-7 w-14 rounded-lg border border-white/12 bg-ink-950/60 px-2 text-center text-cream tabular-nums"
                    />
                  </label>
                </td>
                {days.map((day) => {
                  const taken = grid.get(`${row.roomSlug}|${day}`) ?? 0;
                  const free = row.roomsTotal - taken;
                  const tone =
                    free <= 0
                      ? "bg-wine-600/35 text-wine-100"
                      : taken > 0
                        ? "bg-sand-400/15 text-sand-200"
                        : "text-muted";
                  return (
                    <td key={day} className="px-1 py-1.5 text-center">
                      <span
                        className={`inline-block min-w-8 rounded-md px-1.5 py-1 tabular-nums ${tone}`}
                        title={`Свободно ${Math.max(0, free)} из ${row.roomsTotal}`}
                      >
                        {Math.max(0, free)}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted">
        В клетках — сколько номеров свободно этой ночью. Красное — свободных нет. Число
        «всего» можно поправить прямо здесь: оно снято с настоящей шахматки, но по двум
        категориям это оценка.
      </p>

      {/* ─────────────── Поставить бронь ─────────────── */}
      <h2 className="mt-10 font-display text-2xl text-cream">Поставить бронь руками</h2>
      <p className="mt-2 text-sm text-muted">
        То же самое, что сделал бы администратор на стойке. Консьерж увидит её сразу.
      </p>
      <form onSubmit={create} className="mt-5 grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <label className="lg:col-span-2">
          <span className="text-xs tracking-wide text-muted uppercase">Категория</span>
          <select
            value={form.roomSlug}
            onChange={(e) => setForm({ ...form, roomSlug: e.target.value })}
            className={`mt-2 ${input}`}
          >
            {board.stock.map((s) => (
              <option key={s.roomSlug} value={s.roomSlug}>
                {s.roomName}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="text-xs tracking-wide text-muted uppercase">Номеров</span>
          <input
            type="number"
            min={1}
            value={form.roomsCount}
            onChange={(e) => setForm({ ...form, roomsCount: Number(e.target.value) })}
            className={`mt-2 ${input}`}
          />
        </label>
        <label>
          <span className="text-xs tracking-wide text-muted uppercase">Заезд</span>
          <input
            type="date"
            value={form.checkIn}
            onChange={(e) => {
              const checkIn = e.target.value;
              setForm((f) => ({
                ...f,
                checkIn,
                checkOut: f.checkOut <= checkIn ? addDays(checkIn, 1) : f.checkOut,
              }));
            }}
            className={`mt-2 ${input}`}
          />
        </label>
        <label>
          <span className="text-xs tracking-wide text-muted uppercase">Выезд</span>
          <input
            type="date"
            min={addDays(form.checkIn, 1)}
            value={form.checkOut}
            onChange={(e) => setForm({ ...form, checkOut: e.target.value })}
            className={`mt-2 ${input}`}
          />
        </label>
        <label>
          <span className="text-xs tracking-wide text-muted uppercase">Сумма, ₸</span>
          <input
            type="number"
            min={0}
            step={1000}
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
            className={`mt-2 ${input}`}
          />
        </label>
        <label className="lg:col-span-3">
          <span className="text-xs tracking-wide text-muted uppercase">Гость</span>
          <input
            value={form.guestName}
            onChange={(e) => setForm({ ...form, guestName: e.target.value })}
            placeholder="Кто живёт"
            className={`mt-2 ${input}`}
          />
        </label>
        <label className="lg:col-span-2">
          <span className="text-xs tracking-wide text-muted uppercase">Телефон</span>
          <input
            value={form.guestPhone}
            onChange={(e) => setForm({ ...form, guestPhone: e.target.value })}
            placeholder="+7 701 000 11 22"
            className={`mt-2 ${input}`}
          />
        </label>
        <div className="flex items-end">
          <AdminButton type="submit" disabled={busy}>
            Поставить
          </AdminButton>
        </div>
      </form>
      <p className="mt-2 text-xs text-muted">
        Телефон важен: по нему консьерж в переписке узнаёт «свои» брони. Оставите пустым — в
        чате гость свою бронь не найдёт.
      </p>

      {/* ─────────────── Список ─────────────── */}
      <h2 className="mt-10 font-display text-2xl text-cream">Все брони</h2>
      {board.bookings.length === 0 ? (
        <p className="mt-4 rounded-2xl border border-white/10 bg-ink-900/50 p-6 text-sm text-muted">
          Пока пусто. Поставьте бронь выше или попросите консьержа в переписке.
        </p>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-2xl border border-white/10 bg-ink-900/50">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="text-xs tracking-wide text-muted uppercase">
                <th className="px-4 py-3 text-left font-normal">Номер</th>
                <th className="px-4 py-3 text-left font-normal">Даты</th>
                <th className="px-4 py-3 text-left font-normal">Категория</th>
                <th className="px-4 py-3 text-left font-normal">Гость</th>
                <th className="px-4 py-3 text-right font-normal">Начислено</th>
                <th className="px-4 py-3 text-right font-normal">Оплачено</th>
                <th className="px-4 py-3 text-left font-normal">Откуда</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {board.bookings.map((b) => (
                <tr
                  key={b.ref}
                  className={`border-t border-white/6 ${b.status === "cancelled" ? "opacity-45" : ""}`}
                >
                  <td className="px-4 py-3 whitespace-nowrap text-cream">{b.ref}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {short(b.checkIn)} — {short(b.checkOut)}
                  </td>
                  <td className="px-4 py-3">
                    {b.room}
                    {b.rooms > 1 && <span className="text-muted"> × {b.rooms}</span>}
                  </td>
                  <td className="px-4 py-3">
                    {b.guest || <span className="text-muted">—</span>}
                    {b.phone && <span className="block text-xs text-muted">{b.phone}</span>}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{money.format(b.amount)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {b.paid > 0 ? (
                      <span className="text-sand-200">{money.format(b.paid)}</span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full border px-2.5 py-1 text-xs whitespace-nowrap ${
                        b.origin === "concierge"
                          ? "border-sand-400/40 text-sand-200"
                          : "border-white/15 text-muted"
                      }`}
                    >
                      {b.origin === "concierge"
                        ? "консьерж"
                        : b.origin === "seed"
                          ? "фон"
                          : "руками"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {b.status === "booked" && (
                      <button
                        type="button"
                        onClick={() => act(b.ref, "cancel")}
                        disabled={busy}
                        className="text-xs text-sand-300 underline underline-offset-4"
                      >
                        отменить
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => act(b.ref, "delete")}
                      disabled={busy}
                      className="ml-4 text-xs text-wine-300 underline underline-offset-4"
                    >
                      стереть
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {board.payments.length > 0 && (
        <>
          <h2 className="mt-10 font-display text-2xl text-cream">Принятые платежи</h2>
          <p className="mt-2 text-sm text-muted">
            Что засчитано по присланным квитанциям. Повторную пересылку того же документа
            система не примет второй раз.
          </p>
          <div className="mt-4 grid gap-2">
            {board.payments.map((p, i) => (
              <div
                key={`${p.bookingRef}-${i}`}
                className="rounded-xl border border-white/10 bg-ink-900/50 px-4 py-3 text-sm"
              >
                <span className="text-cream">{p.bookingRef}</span>
                <span className="ml-3 tabular-nums text-sand-200">
                  {money.format(p.amount)} ₸
                </span>
                <span className="ml-3 text-muted">
                  {p.payer || "плательщик не указан"}
                  {p.docNumber && ` · документ ${p.docNumber}`}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
