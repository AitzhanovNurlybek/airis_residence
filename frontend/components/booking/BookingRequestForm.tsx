"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";

import { rooms as fallbackRooms, site, type Room } from "@/lib/site";
import { submitLead, whatsappFallbackUrl, type LeadPayload } from "@/lib/booking";
import { IconWhatsApp } from "@/components/ui/Icons";

const toISO = (d: Date) => d.toISOString().slice(0, 10);
const addDays = (d: Date, n: number) => new Date(d.getTime() + n * 86400000);

type Status = "idle" | "sending" | "ok" | "error";

export function BookingRequestForm({
  rooms = fallbackRooms,
  defaultRoom = "",
  defaultCheckIn,
  defaultCheckOut,
  defaultAdults = 2,
}: {
  rooms?: Room[];
  defaultRoom?: string;
  defaultCheckIn?: string;
  defaultCheckOut?: string;
  defaultAdults?: number;
}) {
  const today = new Date();
  const [form, setForm] = useState<LeadPayload>({
    name: "",
    phone: "",
    email: "",
    checkIn: defaultCheckIn || toISO(addDays(today, 1)),
    checkOut: defaultCheckOut || toISO(addDays(today, 2)),
    adults: defaultAdults,
    room: defaultRoom,
    comment: "",
    company: "",
  });
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");

  const set = <K extends keyof LeadPayload>(key: K, value: LeadPayload[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (status === "sending") return;

    // honeypot: живой человек это поле не видит и не заполняет
    if (form.company) {
      setStatus("ok");
      return;
    }

    setStatus("sending");
    setError("");
    const res = await submitLead(form);
    if (res.ok) {
      setStatus("ok");
    } else {
      setStatus("error");
      setError(res.error ?? "");
    }
  };

  const field =
    "w-full rounded-xl border border-white/12 bg-ink-950/60 px-4 py-3 text-sm text-cream outline-none transition-colors placeholder:text-muted/70 focus:border-sand-400/60 [color-scheme:dark]";
  const label = "mb-2 block text-[0.68rem] tracking-[0.16em] text-sand-400 uppercase";

  if (status === "ok") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-card border border-sand-400/25 bg-ink-900 p-10 text-center"
      >
        <span className="mx-auto grid size-16 place-items-center rounded-full border border-sand-400/40 text-sand-300">
          <svg viewBox="0 0 24 24" className="size-8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="m5 13 4.5 4.5L19 8" />
          </svg>
        </span>
        <h3 className="mt-6 font-display text-2xl text-cream">Заявка отправлена</h3>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed text-muted">
          Свяжемся с вами в течение 15 минут в рабочее время и подтвердим бронь.
          Если нужно быстрее — напишите в WhatsApp.
        </p>
        <a
          href={site.contacts.whatsapp}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-7 inline-flex items-center gap-2 rounded-full bg-[#25D366] px-6 py-3 text-sm font-medium text-white"
        >
          <IconWhatsApp className="size-4" />
          Написать в WhatsApp
        </a>
      </motion.div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-card border border-white/10 bg-ink-900 p-6 md:p-8"
      noValidate
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label className={label} htmlFor="lead-checkin">
            Дата заезда
          </label>
          <input
            id="lead-checkin"
            type="date"
            required
            className={field}
            min={toISO(today)}
            value={form.checkIn}
            onChange={(e) => set("checkIn", e.target.value)}
          />
        </div>

        <div>
          <label className={label} htmlFor="lead-checkout">
            Дата выезда
          </label>
          <input
            id="lead-checkout"
            type="date"
            required
            className={field}
            min={form.checkIn}
            value={form.checkOut}
            onChange={(e) => set("checkOut", e.target.value)}
          />
        </div>

        <div>
          <label className={label} htmlFor="lead-room">
            Тип номера
          </label>
          <select
            id="lead-room"
            className={field}
            value={form.room}
            onChange={(e) => set("room", e.target.value)}
          >
            <option value="">Подберите за меня</option>
            {rooms.map((r) => (
              <option key={r.slug} value={r.slug}>
                {r.shortName}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={label} htmlFor="lead-adults">
            Количество гостей
          </label>
          <select
            id="lead-adults"
            className={field}
            value={form.adults}
            onChange={(e) => set("adults", Number(e.target.value))}
          >
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={label} htmlFor="lead-name">
            Имя
          </label>
          <input
            id="lead-name"
            type="text"
            required
            autoComplete="name"
            placeholder="Как к вам обращаться"
            className={field}
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
          />
        </div>

        <div>
          <label className={label} htmlFor="lead-phone">
            Телефон
          </label>
          <input
            id="lead-phone"
            type="tel"
            required
            autoComplete="tel"
            placeholder="+7 (___) ___-__-__"
            className={field}
            value={form.phone}
            onChange={(e) => set("phone", e.target.value)}
          />
        </div>

        <div className="sm:col-span-2">
          <label className={label} htmlFor="lead-email">
            Почта <span className="normal-case">(необязательно)</span>
          </label>
          <input
            id="lead-email"
            type="email"
            autoComplete="email"
            placeholder="Пришлём подтверждение брони"
            className={field}
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
          />
        </div>

        <div className="sm:col-span-2">
          <label className={label} htmlFor="lead-comment">
            Комментарий
          </label>
          <textarea
            id="lead-comment"
            rows={3}
            placeholder="Ранний заезд, счёт на юрлицо, номер повыше — напишите здесь"
            className={`${field} resize-y`}
            value={form.comment}
            onChange={(e) => set("comment", e.target.value)}
          />
        </div>

        {/* honeypot против спам-ботов */}
        <input
          type="text"
          name="company"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden
          className="absolute -left-[9999px] size-0 opacity-0"
          value={form.company}
          onChange={(e) => set("company", e.target.value)}
        />
      </div>

      <AnimatePresence>
        {status === "error" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-5 rounded-xl border border-wine-400/40 bg-wine-900/30 p-4 text-sm text-wine-200">
              Не удалось отправить заявку{error ? ` (${error})` : ""}. Позвоните по номеру{" "}
              <a href={`tel:${site.contacts.phonePrimaryRaw}`} className="underline">
                {site.contacts.phonePrimary}
              </a>{" "}
              или{" "}
              <a
                href={whatsappFallbackUrl(form, site.contacts.whatsapp)}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                отправьте заявку в WhatsApp
              </a>
              .
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        type="submit"
        disabled={status === "sending"}
        className="mt-7 h-14 w-full rounded-full bg-linear-to-b from-wine-500 to-wine-700 text-[0.95rem] font-medium text-white shadow-[0_12px_34px_-12px_rgba(160,26,84,0.9)] transition-all hover:from-wine-400 hover:to-wine-600 disabled:opacity-60"
      >
        {status === "sending" ? "Отправляем…" : "Отправить заявку"}
      </button>

      <p className="mt-4 text-center text-xs leading-relaxed text-muted">
        Нажимая кнопку, вы соглашаетесь с{" "}
        <a href="/politika-konfidencialnosti" className="underline hover:text-sand-300">
          политикой конфиденциальности
        </a>
        .
      </p>
    </form>
  );
}
