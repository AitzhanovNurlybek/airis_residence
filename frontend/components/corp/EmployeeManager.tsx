"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { buttonClass } from "@/components/ui/Button";
import { formatDate, type Dictionary, type Locale } from "@/lib/corp/dictionary";
import type { CorpUser } from "@/lib/corp/types";

/**
 * Сотрудники компании: кто может бронировать и что видит.
 *
 * Пароль задаёт ответственный и передаёт человеку сам. Почтовой рассылки у нас
 * нет, а рисовать кнопку «отправить приглашение», которая ничего не отправит,
 * нельзя — сотрудник будет ждать письма, которого не будет.
 */
export function EmployeeManager({
  employees,
  meId,
  dict,
  locale,
}: {
  employees: CorpUser[];
  meId: number;
  dict: Dictionary;
  locale: Locale;
}) {
  const router = useRouter();
  const t = dict.employees;

  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(path: string, method: string, body: unknown): Promise<boolean> {
    setBusy(true);
    setError("");
    const res = await fetch(`/api/corp/${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    setBusy(false);

    if (!res || !res.ok) {
      const detail = res ? await res.json().then((d) => d?.detail).catch(() => null) : null;
      setError(typeof detail === "string" ? detail : t.failed);
      return false;
    }
    router.refresh();
    return true;
  }

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const done = await send("employees", "POST", {
      email: String(form.get("email") ?? "").trim(),
      fullName: String(form.get("fullName") ?? "").trim(),
      phone: String(form.get("phone") ?? "").trim(),
      role: String(form.get("role") ?? "employee"),
      password: String(form.get("password") ?? ""),
    });
    if (done) {
      event.currentTarget.reset();
      setAdding(false);
    }
  }

  const field =
    "h-11 w-full rounded-xl border border-ink-600/15 bg-white px-4 text-ink-950 outline-none focus:border-wine-500/60";
  const label = "block text-xs tracking-wide text-ink-700/60 uppercase";

  return (
    <div className="mt-8 grid gap-6">
      {error && (
        <p role="alert" className="rounded-xl bg-wine-50 px-4 py-3 text-sm text-wine-600">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-3xl bg-white shadow-sm">
        <table className="w-full min-w-[46rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-ink-600/10 text-left text-xs text-ink-700/55 uppercase">
              <th className="px-5 py-4 font-normal">{t.fullName}</th>
              <th className="px-5 py-4 font-normal">{t.email}</th>
              <th className="px-5 py-4 font-normal">{t.role}</th>
              <th className="px-5 py-4 font-normal">{t.lastLogin}</th>
              <th className="px-5 py-4" />
            </tr>
          </thead>
          <tbody>
            {employees.map((person) => (
              <tr key={person.id} className="border-b border-ink-600/8 last:border-0">
                <td className="px-5 py-4">
                  {person.fullName || "—"}
                  {!person.isActive && (
                    <span className="mt-1 block text-xs text-ink-700/50">{t.disabled}</span>
                  )}
                  {person.isActive && !person.hasPassword && (
                    <span className="mt-1 block text-xs text-wine-600">{t.noPassword}</span>
                  )}
                </td>
                <td className="px-5 py-4 text-ink-700/80">{person.email}</td>
                <td className="px-5 py-4">
                  <select
                    defaultValue={person.role}
                    disabled={busy || person.id === meId}
                    onChange={(e) =>
                      send(`employees/${person.id}`, "PATCH", { role: e.target.value })
                    }
                    className="rounded-lg border border-ink-600/15 bg-white px-2 py-1 text-sm disabled:opacity-60"
                  >
                    <option value="admin">{t.roleAdmin}</option>
                    <option value="employee">{t.roleEmployee}</option>
                  </select>
                </td>
                <td className="px-5 py-4 text-ink-700/70">
                  {person.lastLoginAt ? formatDate(person.lastLoginAt, locale) : t.never}
                </td>
                <td className="px-5 py-4 text-right whitespace-nowrap">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      const next = window.prompt(t.newPassword);
                      if (next && next.length >= 8) {
                        send(`employees/${person.id}`, "PATCH", { password: next });
                      }
                    }}
                    className="text-xs text-wine-600 underline underline-offset-2 disabled:opacity-50"
                  >
                    {t.setPassword}
                  </button>
                  {/* Себя отключить нельзя: последний ответственный запер бы
                      компанию снаружи. Бэкенд это тоже не даст. */}
                  {person.id !== meId && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        send(`employees/${person.id}`, "PATCH", { isActive: !person.isActive })
                      }
                      className="ml-4 text-xs text-ink-700/70 underline underline-offset-2 disabled:opacity-50"
                    >
                      {person.isActive ? t.disable : t.enable}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {adding ? (
        <form onSubmit={add} className="rounded-3xl bg-white p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className={label} htmlFor="email">
                {t.email}
              </label>
              <input id="email" name="email" type="email" required className={`mt-2 ${field}`} />
            </div>
            <div>
              <label className={label} htmlFor="fullName">
                {t.fullName}
              </label>
              <input id="fullName" name="fullName" className={`mt-2 ${field}`} />
            </div>
            <div>
              <label className={label} htmlFor="phone">
                {t.phone}
              </label>
              <input id="phone" name="phone" type="tel" className={`mt-2 ${field}`} />
            </div>
            <div>
              <label className={label} htmlFor="role">
                {t.role}
              </label>
              <select id="role" name="role" defaultValue="employee" className={`mt-2 ${field}`}>
                <option value="employee">{t.roleEmployee}</option>
                <option value="admin">{t.roleAdmin}</option>
              </select>
            </div>
          </div>
          <label className={`mt-5 ${label}`} htmlFor="password">
            {t.password}
          </label>
          <input
            id="password"
            name="password"
            type="text"
            minLength={8}
            required
            className={`mt-2 ${field}`}
          />
          <p className="mt-2 text-xs text-ink-700/55">{t.passwordHint}</p>

          <div className="mt-6 flex flex-wrap gap-3">
            <button type="submit" disabled={busy} className={buttonClass("primary")}>
              {t.save}
            </button>
            <button type="button" onClick={() => setAdding(false)} className={buttonClass("outline")}>
              {dict.nav.back}
            </button>
          </div>
        </form>
      ) : (
        <div>
          <button type="button" onClick={() => setAdding(true)} className={buttonClass("primary")}>
            + {t.add}
          </button>
          <p className="mt-3 text-xs text-ink-700/55">
            {t.roleAdmin} — {t.roleAdminHint}. {t.roleEmployee} — {t.roleEmployeeHint}.
          </p>
        </div>
      )}
    </div>
  );
}
