"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { buttonClass } from "@/components/ui/Button";
import type { Dictionary } from "@/lib/corp/dictionary";

/** Смена собственного пароля. */
export function PasswordForm({ t }: { t: Dictionary["password"] }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = String(form.get("next") ?? "");
    const repeat = String(form.get("repeat") ?? "");

    // Проверяем до отправки: бэкенд про повтор ничего не знает, он видит
    // только один новый пароль.
    if (next.length < 8) {
      setError(t.tooShort);
      return;
    }
    if (next !== repeat) {
      setError(t.mismatch);
      return;
    }

    setBusy(true);
    setError("");
    const res = await fetch("/api/corp/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: String(form.get("current") ?? ""),
        new_password: next,
      }),
    }).catch(() => null);
    setBusy(false);

    if (!res || !res.ok) {
      setError(res?.status === 400 ? t.wrongCurrent : t.tooShort);
      return;
    }
    event.currentTarget.reset();
    setDone(true);
    router.refresh();
  }

  const field =
    "h-12 w-full rounded-xl border border-ink-600/15 bg-white px-4 text-ink-950 outline-none focus:border-wine-500/60";
  const label = "block text-xs tracking-wide text-ink-700/60 uppercase";

  return (
    <form onSubmit={submit} className="mt-8 max-w-md rounded-3xl bg-white p-6 shadow-sm">
      <label className={label} htmlFor="current">
        {t.current}
      </label>
      <input
        id="current"
        name="current"
        type="password"
        required
        autoComplete="current-password"
        className={`mt-2 ${field}`}
      />

      <label className={`mt-5 ${label}`} htmlFor="next">
        {t.next}
      </label>
      <input
        id="next"
        name="next"
        type="password"
        required
        minLength={8}
        autoComplete="new-password"
        className={`mt-2 ${field}`}
      />

      <label className={`mt-5 ${label}`} htmlFor="repeat">
        {t.repeat}
      </label>
      <input
        id="repeat"
        name="repeat"
        type="password"
        required
        minLength={8}
        autoComplete="new-password"
        className={`mt-2 ${field}`}
      />

      {error && (
        <p role="alert" className="mt-4 text-sm text-wine-600">
          {error}
        </p>
      )}
      {done && !error && <p className="mt-4 text-sm text-emerald-700">{t.done}</p>}

      <button type="submit" disabled={busy} className={buttonClass("primary", "md", "mt-6 w-full")}>
        {t.submit}
      </button>
    </form>
  );
}
