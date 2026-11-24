"use client";

import { useEffect, useRef, useState } from "react";

import { site } from "@/lib/site";

/**
 * Чат с виртуальным администратором на стойке («Отель в 3D»).
 *
 * Отвечает тот же консьерж, что в WhatsApp, через /api/chat → бэкенд
 * /api/web-chat (канал `web`: только номера, наличие с ценой и ссылка на
 * бронь; пределы на визит, адрес и сутки). История живёт на сервере по
 * идентификатору визита; здесь — только копия для показа, чтобы переписка не
 * пропадала, если гость сходил посмотреть этажи и вернулся к стойке.
 */

export const ASSISTANT_NAME = "Алия";

const STORE_ID = "airis-chat-id";
const STORE_LOG = "airis-chat-log";
const SUGGEST = [
  "Сколько стоит номер на выходные?",
  "Во сколько заезд и выезд?",
  "Есть ли парковка?",
  "Как добраться из аэропорта?",
];
const GREETING = `Здравствуйте! Я ${ASSISTANT_NAME}, виртуальный администратор Airis Residence. Спросите меня о номерах, ценах, заезде или о том, что рядом с отелем.`;
const FALLBACK = `Не получилось ответить. Напишите нам в WhatsApp ${site.contacts.whatsapp} — мы на связи круглосуточно.`;

type Photo = { url: string; room: string };
type Msg = { role: "user" | "assistant"; text: string; photos?: Photo[] };

function visitId(): string {
  try {
    const known = sessionStorage.getItem(STORE_ID);
    if (known) return known;
    const id = crypto.randomUUID();
    sessionStorage.setItem(STORE_ID, id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

function loadLog(): Msg[] {
  try {
    const raw = sessionStorage.getItem(STORE_LOG);
    const list = raw ? (JSON.parse(raw) as Msg[]) : [];
    return Array.isArray(list) ? list.slice(-40) : [];
  } catch {
    return [];
  }
}

/** Текст с кликабельными ссылками. Разметку модель не пишет (запрещено правилами). */
function Linked({ text }: { text: string }) {
  const parts = text.split(/(https?:\/\/[^\s<>"]+)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (!/^https?:\/\//.test(part)) return <span key={i}>{part}</span>;
        const url = part.replace(/[.,;:!?)]+$/, "");
        const tail = part.slice(url.length);
        let label = url;
        try {
          const u = new URL(url);
          label = u.hostname.includes("wa.me")
            ? "WhatsApp"
            : u.pathname.includes("book")
              ? "Забронировать"
              : u.hostname + u.pathname;
        } catch {
          /* как есть */
        }
        return (
          <span key={i}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="break-all text-sand-200 underline underline-offset-2"
            >
              {label}
            </a>
            {tail}
          </span>
        );
      })}
    </>
  );
}

export function ReceptionChat({ className = "" }: { className?: string }) {
  const [log, setLog] = useState<Msg[]>(loadLog);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORE_LOG, JSON.stringify(log.slice(-40)));
    } catch {
      /* без хранилища просто не запомним */
    }
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log, busy]);

  async function send(raw: string) {
    const text = raw.trim().slice(0, 500);
    if (!text || busy) return;
    setLog((l) => [...l, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: visitId(), message: text }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        text?: string;
        photos?: Photo[];
      };
      const reply =
        typeof data.text === "string" && data.text.trim()
          ? data.text.trim()
          : FALLBACK;
      setLog((l) => [
        ...l,
        { role: "assistant", text: reply, photos: data.photos?.slice(0, 4) },
      ]);
    } catch {
      setLog((l) => [...l, { role: "assistant", text: FALLBACK }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`flex flex-col overflow-hidden rounded-2xl border border-white/12 bg-ink-950/92 text-cream shadow-lift ${className}`}
    >
      <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
        <span className="relative grid h-9 w-9 shrink-0 place-items-center rounded-full bg-sand-300 font-display text-base text-ink-950">
          {ASSISTANT_NAME[0]}
          <span className="absolute -right-0.5 -bottom-0.5 h-3 w-3 rounded-full border-2 border-ink-950 bg-[#25D366]" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium">{ASSISTANT_NAME}</p>
          <p className="text-[0.7rem] text-muted">
            Виртуальный администратор · ИИ
          </p>
        </div>
      </div>

      <div
        ref={listRef}
        className="flex-1 space-y-2.5 overflow-y-auto overscroll-contain px-4 py-3 text-sm leading-relaxed"
      >
        <p className="max-w-[88%] rounded-2xl rounded-tl-md bg-white/8 px-3.5 py-2.5">
          {GREETING}
        </p>
        {log.map((m, i) =>
          m.role === "user" ? (
            <p
              key={i}
              className="ml-auto max-w-[85%] rounded-2xl rounded-tr-md bg-sand-300 px-3.5 py-2.5 text-ink-950"
            >
              {m.text}
            </p>
          ) : (
            <div key={i} className="max-w-[88%]">
              <p className="rounded-2xl rounded-tl-md bg-white/8 px-3.5 py-2.5 whitespace-pre-line">
                <Linked text={m.text} />
              </p>
              {m.photos && m.photos.length > 0 && (
                <div className="mt-1.5 flex gap-1.5">
                  {m.photos.map((p) => (
                    <a
                      key={p.url}
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={p.url}
                        alt={p.room}
                        loading="lazy"
                        className="h-16 w-20 rounded-lg object-cover"
                      />
                    </a>
                  ))}
                </div>
              )}
            </div>
          ),
        )}
        {busy && (
          <p
            className="flex w-fit items-center gap-1 rounded-2xl rounded-tl-md bg-white/8 px-3.5 py-3"
            aria-label={`${ASSISTANT_NAME} печатает`}
          >
            {[0, 1, 2].map((k) => (
              <span
                key={k}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-cream/70"
                style={{ animationDelay: `${k * 120}ms` }}
              />
            ))}
          </p>
        )}
      </div>

      {log.length === 0 && (
        <div className="flex flex-wrap gap-1.5 px-4 pb-2">
          {SUGGEST.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => send(s)}
              className="rounded-full border border-white/15 px-3 py-1.5 text-[0.72rem] text-cream/85 transition-colors hover:border-sand-300/60 hover:text-cream"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex gap-2 border-t border-white/10 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={500}
          placeholder="Спросите о номерах, ценах, заезде…"
          aria-label={`Сообщение для ${ASSISTANT_NAME}`}
          className="min-w-0 flex-1 rounded-full border border-white/12 bg-white/5 px-4 py-2.5 text-sm text-cream placeholder:text-muted focus:border-sand-300/60 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="shrink-0 rounded-full bg-sand-300 px-4 text-sm font-medium text-ink-950 transition-colors hover:bg-sand-200 disabled:opacity-50"
        >
          Отправить
        </button>
      </form>
      <p className="px-4 pb-3 text-[0.65rem] leading-snug text-muted">
        Отвечает ИИ и может ошибаться: точные условия подтвердит стойка. Не
        пишите сюда номера документов и карт.
      </p>
    </div>
  );
}
