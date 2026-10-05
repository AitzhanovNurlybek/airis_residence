"use client";

import { useState } from "react";

import { buttonClass } from "@/components/ui/Button";

/**
 * Форма отзыва. Отзыв сохраняется в базе и появляется на сайте после
 * проверки сотрудником — гостю это говорим сразу, чтобы он не искал свой
 * текст на странице и не отправлял второй раз.
 */
export function ReviewForm() {
  const [stars, setStars] = useState(5);
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setState("sending");
    setError("");
    try {
      const res = await fetch("/api/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: String(form.get("name") || ""),
          text: String(form.get("text") || ""),
          stay: String(form.get("stay") || ""),
          contact: String(form.get("contact") || ""),
          website: String(form.get("website") || ""),
          stars,
        }),
      });
      if (res.ok) {
        setState("done");
        return;
      }
      const data = await res.json().catch(() => ({}));
      const detail = (data as { detail?: unknown }).detail;
      setError(
        typeof detail === "string"
          ? detail
          : res.status === 422
            ? "Проверьте поля: имя — от 2 букв, отзыв — от 10 символов."
            : "Не получилось отправить. Попробуйте ещё раз.",
      );
      setState("error");
    } catch {
      setError("Нет связи. Попробуйте ещё раз.");
      setState("error");
    }
  }

  if (state === "done") {
    return (
      <p className="rounded-xl border border-sand-400/30 bg-sand-300/5 px-5 py-4 text-sm leading-relaxed text-cream">
        Спасибо за отзыв! Он появится на сайте после проверки — обычно в течение дня.
      </p>
    );
  }

  const field =
    "w-full rounded-xl border border-white/12 bg-ink-950/60 px-4 py-3 text-sm text-cream placeholder:text-muted/70 focus:border-sand-400/60 focus:outline-none";

  return (
    <form onSubmit={submit} className="grid gap-3">
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted">Оценка:</span>
        <div role="radiogroup" aria-label="Оценка" className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={stars === n}
              aria-label={`${n} из 5`}
              onClick={() => setStars(n)}
              className={`text-2xl leading-none transition-colors ${n <= stars ? "text-sand-400" : "text-white/20 hover:text-white/40"}`}
            >
              ★
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <input name="name" required minLength={2} maxLength={80} placeholder="Ваше имя" className={field} />
        <input name="stay" maxLength={60} placeholder="Когда жили: «сентябрь 2026»" className={field} />
      </div>
      <textarea
        name="text"
        required
        minLength={10}
        maxLength={1500}
        rows={4}
        placeholder="Что понравилось, что стоит улучшить"
        className={field}
      />
      <input
        name="contact"
        maxLength={120}
        placeholder="Телефон или почта (не публикуется)"
        className={field}
      />
      {/* Ловушка для ботов: человек это поле не видит. */}
      <input name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" className="hidden" />
      {error && <p className="text-sm text-wine-200">{error}</p>}
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          disabled={state === "sending"}
          className={buttonClass("primary", "md", "disabled:opacity-60")}
        >
          {state === "sending" ? "Отправляем…" : "Отправить отзыв"}
        </button>
        <span className="text-xs text-muted">Отзыв появится после проверки.</span>
      </div>
    </form>
  );
}
