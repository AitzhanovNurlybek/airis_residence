"use client";

import { useRef, useState } from "react";

import { AdminButton } from "@/components/admin/ui";

/**
 * Переписка с консьержем — то же, что придёт из WhatsApp.
 *
 * Телефон задаётся полем сверху, и это здесь главное. Консьерж решает, чьи
 * брони показывать, именно по нему: поменяли номер — стали другим человеком.
 * Так проверяется, что чужую бронь он не отдаст, сколько его ни проси.
 *
 * Под каждым ответом видно, в какие инструменты он полез. Без этого непонятно,
 * посмотрел он в шахматку или сочинил ответ по памяти.
 */

type Turn = { who: "guest" | "hotel"; text: string; tools: string[] };

const PHONES = [
  { label: "Гость (Данияр)", value: "+7 701 000 11 22" },
  { label: "Другой гость", value: "+7 705 999 88 77" },
  { label: "Неизвестный номер", value: "+7 777 111 22 33" },
];

const SAMPLES = [
  "Есть свободные номера на завтра-послезавтра?",
  "Хочу забронировать Comfort на эти даты",
  "Напомните, какая у меня бронь?",
  "Сколько стоит самый дешёвый номер?",
  "Отмените мою бронь",
];

export function ConciergeChat() {
  const [phone, setPhone] = useState(PHONES[0].value);
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // История в том виде, в каком её ждёт модель. Держим в ref: она нужна
  // следующему запросу, но перерисовывать из-за неё нечего.
  const history = useRef<unknown[]>([]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;

    setDraft("");
    setError("");
    setBusy(true);
    setTurns((t) => [...t, { who: "guest", text: message, tools: [] }]);

    try {
      const res = await fetch("/api/admin/local/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, phone, history: history.current }),
      });
      if (!res.ok) throw new Error(`Сервер ответил ${res.status}`);
      const data = await res.json();

      history.current = data.history ?? [];
      setTurns((t) => [
        ...t,
        {
          who: "hotel",
          text: data.text,
          tools: (data.toolCalls ?? []).map((c: { name: string }) => c.name),
        },
      ]);
      if (!data.ok && data.reason) setError(data.reason);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отправить");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    history.current = [];
    setTurns([]);
    setError("");
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <label className="min-w-64">
          <span className="text-xs tracking-wide text-muted uppercase">Кто пишет</span>
          <select
            value={phone}
            onChange={(e) => {
              setPhone(e.target.value);
              reset();
            }}
            className="mt-2 h-10 w-full rounded-xl border border-white/12 bg-ink-950/60 px-3 text-sm text-cream outline-none focus:border-sand-400/60"
          >
            {PHONES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label} — {p.value}
              </option>
            ))}
          </select>
        </label>
        <AdminButton type="button" variant="secondary" onClick={reset} disabled={busy}>
          Начать заново
        </AdminButton>
      </div>
      <p className="mt-2 text-xs text-muted">
        Смена номера начинает разговор с нуля — как будто написал другой человек. Свои брони
        консьерж узнаёт именно по телефону.
      </p>

      <div className="mt-6 min-h-72 rounded-2xl border border-white/10 bg-ink-900/50 p-5">
        {turns.length === 0 ? (
          <p className="text-sm text-muted">
            Напишите как гость. Ответ придёт такой же, каким уйдёт в WhatsApp.
          </p>
        ) : (
          <div className="grid gap-4">
            {turns.map((turn, i) => (
              <div
                key={i}
                className={turn.who === "guest" ? "flex justify-end" : "flex justify-start"}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                    turn.who === "guest"
                      ? "bg-wine-700/40 text-cream"
                      : "border border-white/10 bg-ink-950/60 text-cream/90"
                  }`}
                >
                  {turn.text}
                  {turn.who === "hotel" && (
                    <span className="mt-2 block text-xs text-muted">
                      {turn.tools.length
                        ? `смотрел в шахматку: ${turn.tools.join(", ")}`
                        : "по справке, без обращения к шахматке"}
                    </span>
                  )}
                </div>
              </div>
            ))}
            {busy && <p className="text-sm text-muted">печатает…</p>}
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 rounded-xl bg-wine-600/15 px-4 py-3 text-sm text-wine-200">
          {error}
        </p>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(draft);
        }}
        className="mt-4 flex gap-3"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Сообщение от гостя"
          disabled={busy}
          className="h-11 flex-1 rounded-xl border border-white/12 bg-ink-950/60 px-4 text-sm text-cream outline-none focus:border-sand-400/60"
        />
        <AdminButton type="submit" disabled={busy || !draft.trim()}>
          {busy ? "Ждём…" : "Отправить"}
        </AdminButton>
      </form>

      <div className="mt-4 flex flex-wrap gap-2">
        {SAMPLES.map((sample) => (
          <button
            key={sample}
            type="button"
            onClick={() => void send(sample)}
            disabled={busy}
            className="rounded-full border border-white/12 px-3 py-1.5 text-xs text-muted transition-colors hover:border-sand-400/50 hover:text-cream disabled:opacity-40"
          >
            {sample}
          </button>
        ))}
      </div>
    </div>
  );
}
