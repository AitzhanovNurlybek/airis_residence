"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AdminButton, Field, inputClass } from "@/components/admin/ui";
import { Logo } from "@/components/ui/Logo";

export function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");

    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }).catch(() => null);

    if (!res) {
      setError("Сервер не отвечает");
      setBusy(false);
      return;
    }

    if (res.ok) {
      router.replace("/admin");
      router.refresh();
      return;
    }

    const data = await res.json().catch(() => ({}));
    setError(data.error ?? "Не удалось войти");
    setBusy(false);
  };

  return (
    <div className="grid min-h-dvh place-items-center px-5">
      <form onSubmit={submit} className="w-full max-w-sm">
        <Logo className="mx-auto h-11 w-auto" />
        <h1 className="mt-8 text-center font-display text-2xl text-cream">
          Управление сайтом
        </h1>
        <p className="mt-2 text-center text-sm text-muted">
          Здесь меняются цены, описания и фотографии номеров
        </p>

        <div className="mt-8 space-y-4">
          <Field label="Логин">
            <input
              className={inputClass}
              value={username}
              autoComplete="username"
              onChange={(e) => setUsername(e.target.value)}
            />
          </Field>
          <Field label="Пароль">
            <input
              className={inputClass}
              type="password"
              value={password}
              autoComplete="current-password"
              autoFocus
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
        </div>

        {error && (
          <p className="mt-4 rounded-xl border border-wine-400/40 bg-wine-900/30 px-4 py-3 text-sm text-wine-100">
            {error}
          </p>
        )}

        <AdminButton type="submit" className="mt-6 w-full" disabled={busy}>
          {busy ? "Проверяем…" : "Войти"}
        </AdminButton>
      </form>
    </div>
  );
}
