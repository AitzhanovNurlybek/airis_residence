"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { buttonClass } from "@/components/ui/Button";
import { formatMoney, formatNights, type Dictionary, type Locale } from "@/lib/corp/dictionary";
import type { CorpRoom } from "@/lib/corp/types";

/**
 * Подбор номеров и оформление заявки.
 *
 * Наличие номеров здесь не проверяется и показывать его нечем: система
 * бронирования отеля API не отдаёт. Поэтому экран честно считает деньги по
 * корпоративному прайсу и отправляет заявку, а номер подтверждает менеджер —
 * ровно об этом плашка сверху.
 *
 * Проверки продублированы с бэкендом намеренно. Серверные — источник правды,
 * без них форму можно обойти; клиентские нужны, чтобы человек узнал о проблеме
 * до отправки, а не после.
 */

const today = () => new Date().toISOString().slice(0, 10);

function nightsBetween(from: string, to: string): number {
  if (!from || !to) return 0;
  const ms = new Date(to).getTime() - new Date(from).getTime();
  return ms > 0 ? Math.round(ms / 86_400_000) : 0;
}

function Counter({
  value,
  onChange,
  labelMinus,
  labelPlus,
  min = 0,
}: {
  value: number;
  onChange: (next: number) => void;
  labelMinus: string;
  labelPlus: string;
  /** Нижняя граница. Без неё минус у взрослых оставался активным на единице
      и на нажатие не отвечал — кнопка, которая ничего не делает. */
  min?: number;
}) {
  const btn =
    "grid size-9 place-items-center rounded-full border border-ink-600/20 text-lg leading-none text-ink-900 transition-colors hover:border-wine-500/60 disabled:opacity-30";
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        className={btn}
        aria-label={labelMinus}
        disabled={value <= min}
        onClick={() => onChange(value - 1)}
      >
        −
      </button>
      <span className="w-6 text-center tabular-nums">{value}</span>
      <button type="button" className={btn} aria-label={labelPlus} onClick={() => onChange(value + 1)}>
        +
      </button>
    </div>
  );
}

export function BookingComposer({
  rooms,
  dict,
  locale,
  hotelName,
  hotelCity,
  breakfastPrice,
}: {
  rooms: CorpRoom[];
  dict: Dictionary;
  locale: Locale;
  hotelName: string;
  hotelCity: string;
  /** Вычет за отказ от завтрака: на гостя за ночь, из договора компании. */
  breakfastPrice: number;
}) {
  const router = useRouter();
  const t = dict.booking;

  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [adults, setAdults] = useState(1);
  const [children, setChildren] = useState(0);
  const [mealPlan, setMealPlan] = useState<"breakfast" | "none">("breakfast");
  const [picked, setPicked] = useState<Record<string, number>>({});
  const [guestName, setGuestName] = useState("");
  const [guestPhone, setGuestPhone] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const nights = nightsBetween(checkIn, checkOut);

  const { capacity, total, lines } = useMemo(() => {
    let capacity = 0;
    let total = 0;
    const lines: { room: CorpRoom; count: number; amount: number }[] = [];
    for (const room of rooms) {
      const count = picked[room.slug] ?? 0;
      if (count <= 0) continue;
      const amount = room.corpPrice * count * Math.max(nights, 0);
      capacity += room.capacity * count;
      total += amount;
      lines.push({ room, count, amount });
    }
    return { capacity, total, lines };
  }, [rooms, picked, nights]);

  const guests = adults + children;

  // Вычет считается здесь, а не внутри useMemo с номерами: он зависит от
  // числа гостей и ночей, а не от выбранных категорий. Держать его отдельно
  // дешевле, чем пересчитывать всю корзину при каждом нажатии «+».
  //
  // Бэкенд считает сумму заново и не доверяет нашей: здесь она только для
  // показа. Расхождение возможно, если менеджер поменяет договор, пока
  // сотрудник заполняет форму, — и правым должен быть бэкенд.
  const mealDeduction =
    mealPlan === "none" && breakfastPrice > 0 && nights > 0
      ? Math.min(total, breakfastPrice * guests * nights)
      : 0;
  const payable = total - mealDeduction;

  function validate(): string {
    if (!checkIn || !checkOut) return t.needDates;
    if (nights <= 0) return t.badOrder;
    if (checkIn < today()) return t.inPast;
    if (lines.length === 0) return t.nothingPicked;
    if (guests > capacity) return t.notEnough;
    return "";
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }

    setBusy(true);
    setError("");
    const res = await fetch("/api/corp/bookings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        checkIn,
        checkOut,
        adults,
        children,
        guestName: guestName.trim(),
        guestPhone: guestPhone.trim(),
        comment: comment.trim(),
        mealPlan,
        items: lines.map((line) => ({ roomSlug: line.room.slug, roomsCount: line.count })),
      }),
    }).catch(() => null);

    if (!res || !res.ok) {
      // Бэкенд объясняет отказ по-человечески («вмещают 2 гостей, а в заявке 5»),
      // и его текст полезнее нашего общего. Свой показываем, только если
      // разобрать ответ не вышло.
      const detail = res ? await res.json().then((d) => d?.detail).catch(() => null) : null;
      setError(typeof detail === "string" ? detail : t.failed);
      setBusy(false);
      return;
    }

    router.push("/corp/bookings");
    router.refresh();
  }

  const field =
    "h-12 w-full rounded-xl border border-ink-600/15 bg-white px-4 text-ink-950 outline-none focus:border-wine-500/60";
  const label = "block text-xs tracking-wide text-ink-700/60 uppercase";
  const labelOnWine = "block text-xs tracking-wide text-white/70 uppercase";

  return (
    <form onSubmit={submit} className="mt-8 grid gap-6 lg:grid-cols-[1fr_20rem] lg:items-start">
      <div className="grid gap-6">
        <div className="inline-flex flex-col rounded-2xl bg-wine-500 px-5 py-3 text-white">
          <span className="font-medium">{hotelName}</span>
          <span className="text-xs text-white/70">{hotelCity}</span>
        </div>

        <section className="rounded-3xl bg-wine-500 p-6 text-white shadow-sm">
          <h2 className="font-display text-xl">{t.dates}</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className={labelOnWine} htmlFor="checkIn">
                {t.checkIn}
              </label>
              <input
                id="checkIn"
                type="date"
                min={today()}
                value={checkIn}
                onChange={(e) => setCheckIn(e.target.value)}
                className={`mt-2 ${field}`}
              />
            </div>
            <div>
              <label className={labelOnWine} htmlFor="checkOut">
                {t.checkOut}
              </label>
              <input
                id="checkOut"
                type="date"
                min={checkIn || today()}
                value={checkOut}
                onChange={(e) => setCheckOut(e.target.value)}
                className={`mt-2 ${field}`}
              />
            </div>
          </div>

          <h2 className="mt-7 font-display text-xl">{t.guests}</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 text-ink-950">
              <span className="text-sm">{t.adults}</span>
              <Counter
                value={adults}
                min={1}
                onChange={(n) => setAdults(Math.max(1, n))}
                labelMinus={`${t.adults} −`}
                labelPlus={`${t.adults} +`}
              />
            </div>
            <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 text-ink-950">
              <span className="text-sm">{t.children}</span>
              <Counter
                value={children}
                onChange={(n) => setChildren(Math.max(0, n))}
                labelMinus={`${t.children} −`}
                labelPlus={`${t.children} +`}
              />
            </div>
          </div>

          <h2 className="mt-7 font-display text-xl">{t.meals}</h2>
          {/* Радиокнопки, а не выпадающий список: вариантов всего два, и
              скрывать половину выбора за кликом незачем. */}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {(["breakfast", "none"] as const).map((option) => {
              const chosen = mealPlan === option;
              return (
                <label
                  key={option}
                  // Разрыв между состояниями намеренно большой. На малиновом
                  // фоне полупрозрачная плашка сама по себе выглядит розовой
                  // и подсвеченной — при мягкой разнице невыбранный вариант
                  // читался как выбранный.
                  className={`flex cursor-pointer items-center gap-3 rounded-xl px-4 py-3 transition-colors ${
                    chosen
                      ? "bg-white text-ink-950 shadow-sm ring-2 ring-ink-950/20"
                      : "bg-white/25 text-cream/80 hover:bg-white/40"
                  }`}
                >
                  <input
                    type="radio"
                    name="mealPlan"
                    value={option}
                    checked={chosen}
                    onChange={() => setMealPlan(option)}
                    className="h-4 w-4 accent-wine-500"
                  />
                  <span className="text-sm">
                    {option === "breakfast" ? t.mealBreakfast : t.mealNone}
                  </span>
                </label>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-cream/70">
            {breakfastPrice > 0
              ? `${t.mealNotePaid}: ${formatMoney(breakfastPrice)} ${dict.common.currency}`
              : t.mealNoteFree}
          </p>
        </section>

        <section>
          <h2 className="font-display text-2xl">{t.pickRooms}</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {rooms.map((room) => {
              const count = picked[room.slug] ?? 0;
              const tooSmall = guests > room.capacity * Math.max(count, 1);
              const saving = room.publicPrice - room.corpPrice;
              return (
                <article
                  key={room.slug}
                  className={`overflow-hidden rounded-2xl bg-white shadow-sm ring-1 transition-shadow ${
                    count > 0 ? "ring-wine-500/50" : "ring-transparent"
                  }`}
                >
                  {/* Обычный img, а не next/image: оптимизатор на Vercel выключен
                      (images.unoptimized), исходники ужаты заранее, и next/image
                      потребовал бы прописанного домена хранилища ни за чем. */}
                  {room.images[0] && (
                    <div className="relative">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={room.images[0]}
                        alt={room.shortName}
                        loading="lazy"
                        className="h-40 w-full object-cover"
                      />
                      {room.images.length > 1 && (
                        <span className="absolute top-3 right-3 rounded-md bg-ink-950/70 px-2 py-1 text-[0.65rem] text-white">
                          {room.images.length} фото
                        </span>
                      )}
                    </div>
                  )}
                  <div className="p-5">
                    <h3 className="font-display text-lg">{room.shortName}</h3>
                    <p className="mt-1 text-xs text-ink-700/60">
                      {room.area} · {room.capacity} · {room.beds}
                    </p>

                    <p className="mt-3">
                      <span className="font-display text-xl text-wine-500">
                        {formatMoney(room.corpPrice)} {dict.common.currency}
                      </span>
                      <span className="ml-2 text-xs text-ink-700/55">{t.perNightShort}</span>
                    </p>
                    {saving > 0 && (
                      <p className="mt-1 text-xs text-ink-700/50">
                        {dict.common.sitePrice}{" "}
                        <s>
                          {formatMoney(room.publicPrice)} {dict.common.currency}
                        </s>
                      </p>
                    )}

                    {tooSmall && <p className="mt-3 text-xs text-wine-600">{t.tooSmall}</p>}

                    <a
                      href={`/nomera/${room.slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 inline-block text-xs text-wine-600 underline underline-offset-2"
                    >
                      {t.details}
                    </a>

                    <div className="mt-4 flex items-center justify-between">
                      <span className="text-xs text-ink-700/60">{t.count}</span>
                      <Counter
                        value={count}
                        onChange={(next) =>
                          setPicked((prev) => ({ ...prev, [room.slug]: Math.max(0, next) }))
                        }
                        labelMinus={`${room.shortName} −`}
                        labelPlus={`${room.shortName} +`}
                      />
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="rounded-3xl bg-white p-6 shadow-sm">
          <h2 className="font-display text-xl">{t.guest}</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className={label} htmlFor="guestName">
                {t.guestName}
              </label>
              <input
                id="guestName"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                className={`mt-2 ${field}`}
              />
            </div>
            <div>
              <label className={label} htmlFor="guestPhone">
                {t.guestPhone}
              </label>
              <input
                id="guestPhone"
                type="tel"
                value={guestPhone}
                onChange={(e) => setGuestPhone(e.target.value)}
                className={`mt-2 ${field}`}
              />
            </div>
          </div>
          <label className={`mt-5 ${label}`} htmlFor="comment">
            {t.comment}
          </label>
          <textarea
            id="comment"
            rows={3}
            placeholder={t.commentHint}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="mt-2 w-full rounded-xl border border-ink-600/15 bg-white px-4 py-3 text-ink-950 outline-none focus:border-wine-500/60"
          />
        </section>
      </div>

      {/* Итог держится на виду при прокрутке: человек добавляет номера и сразу
          видит, во что это обходится, не возвращаясь наверх. */}
      <aside className="rounded-3xl bg-white p-6 shadow-sm lg:sticky lg:top-24">
        <h2 className="font-display text-xl">{t.summary}</h2>

        {lines.length === 0 ? (
          <p className="mt-4 text-sm text-ink-700/60">{t.nothingPicked}</p>
        ) : (
          <ul className="mt-4 space-y-3 text-sm">
            {lines.map((line) => (
              <li key={line.room.slug} className="flex justify-between gap-3">
                <span className="text-ink-700/80">
                  {line.room.shortName} × {line.count}
                </span>
                <span className="whitespace-nowrap tabular-nums">
                  {nights > 0
                    ? `${formatMoney(line.amount)} ${dict.common.currency}`
                    : `${formatMoney(line.room.corpPrice)} ${dict.common.currency} / ${t.perNightShort}`}
                </span>
              </li>
            ))}
          </ul>
        )}

        {nights > 0 && (
          <p className="mt-4 border-t border-ink-600/10 pt-4 text-xs text-ink-700/60">
            {formatNights(nights, dict, locale)}
            {lines.length > 0 && ` · ${t.capacityLeft}: ${capacity}`}
          </p>
        )}

        {mealDeduction > 0 && (
          <p className="mt-3 flex items-baseline justify-between text-sm">
            <span className="text-ink-700/70">{t.mealDiscountLine}</span>
            <span className="tabular-nums text-ink-700">
              −{formatMoney(mealDeduction)} {dict.common.currency}
            </span>
          </p>
        )}

        <p className="mt-4 flex items-baseline justify-between border-t border-ink-600/10 pt-4">
          <span className="text-sm text-ink-700/70">{t.summary}</span>
          {/* Без дат ночей ноль, и сумма вышла бы «0 ₸» — читается как
              «бесплатно». Пока дат нет, честнее прочерк. */}
          <span className="font-display text-2xl text-wine-500 tabular-nums">
            {nights > 0 && lines.length > 0
              ? `${formatMoney(payable)} ${dict.common.currency}`
              : "—"}
          </span>
        </p>

        {error && (
          <p role="alert" className="mt-4 text-sm text-wine-600">
            {error}
          </p>
        )}

        <button type="submit" disabled={busy} className={buttonClass("primary", "md", "mt-5 w-full")}>
          {busy ? t.submitting : t.submit}
        </button>
        <p className="mt-3 text-xs leading-relaxed text-ink-700/55">{dict.notice}</p>
      </aside>
    </form>
  );
}
