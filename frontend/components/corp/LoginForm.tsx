"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { buttonClass } from "@/components/ui/Button";
import type { Dictionary } from "@/lib/corp/dictionary";
import { site } from "@/lib/site";

type Texts = Dictionary["login"] & { loading: string };

/**
 * Форма входа в кабинет.
 *
 * Текст ошибки один и тот же на неверную почту и на неверный пароль — так
 * отвечает и бэкенд. Иначе форму можно использовать как справочник
 * «эта компания у вас обслуживается».
 */
export function LoginForm({ t }: { t: Texts }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");

    const form = new FormData(event.currentTarget);
    const res = await fetch("/api/corp/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: String(form.get("email") ?? "").trim(),
        password: String(form.get("password") ?? ""),
      }),
    }).catch(() => null);

    if (!res) {
      setError(t.offline);
      setBusy(false);
      return;
    }
    if (!res.ok) {
      setError(t.failed);
      setBusy(false);
      return;
    }

    // replace, а не push: кнопка «назад» не должна возвращать на форму входа,
    // с которой человек уже ушёл.
    router.replace("/corp");
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="w-full max-w-md rounded-3xl bg-white p-7 shadow-xl">
      <label className="block text-xs tracking-wide text-ink-700/70 uppercase" htmlFor="email">
        {t.email}
      </label>
      <input
        id="email"
        name="email"
        type="email"
        required
        autoComplete="username"
        autoFocus
        className="mt-2 h-12 w-full rounded-xl border border-ink-600/15 bg-sand-100/60 px-4 text-ink-950 outline-none focus:border-wine-500/60"
      />

      <label
        className="mt-5 block text-xs tracking-wide text-ink-700/70 uppercase"
        htmlFor="password"
      >
        {t.password}
      </label>
      <input
        id="password"
        name="password"
        type="password"
        required
        autoComplete="current-password"
        className="mt-2 h-12 w-full rounded-xl border border-ink-600/15 bg-sand-100/60 px-4 text-ink-950 outline-none focus:border-wine-500/60"
      />

      {error && (
        <p role="alert" className="mt-4 text-sm text-wine-600">
          {error}
        </p>
      )}

      <button type="submit" disabled={busy} className={buttonClass("primary", "md", "mt-6 w-full")}>
        {busy ? t.loading : t.submit}
      </button>

      <button
        type="button"
        onClick={() => setHint((v) => !v)}
        className="mt-4 block text-sm text-wine-600 underline underline-offset-4"
      >
        {t.forgot}
      </button>
      {/* Контакты берутся из site.ts, а не вписаны в перевод: телефон отеля
          лежит в одном месте, и три языковые копии разошлись бы при первой
          же смене номера. */}
      {hint && (
        <p className="mt-2 text-sm leading-relaxed text-ink-700/80">
          {t.forgotHint}{" "}
          <a
            href={`tel:${site.contacts.phonePrimaryRaw}`}
            className="whitespace-nowrap text-wine-600 underline underline-offset-4"
          >
            {site.contacts.phonePrimary}
          </a>
          {" · "}
          <a
            href={`mailto:${site.contacts.email}`}
            className="text-wine-600 underline underline-offset-4"
          >
            {site.contacts.email}
          </a>
        </p>
      )}
    </form>
  );
}
