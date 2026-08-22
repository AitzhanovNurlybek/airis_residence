"use client";

import { useMemo, useState } from "react";

import { adminSend, AdminError } from "@/lib/adminClient";
import { LEAD_STATUSES, type AdminLead, type AdminRoom } from "@/lib/adminTypes";
import { useToast } from "@/components/admin/ui";

const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * Срочность заявки.
 *
 * Появилось после того, как шесть настоящих заявок пролежали неотвеченными: в
 * общем списке они выглядели ровно как проверочные и как давно закрытые. Когда
 * всё одинаковое, глазу не за что зацепиться, и заявка с заездом завтра теряется
 * среди прошлогодних.
 *
 * Считаем по дате заезда, а не по дате обращения: гостю важно, когда он
 * приедет, а не когда написал.
 */
type Urgency = "burning" | "soon" | "normal" | "stale" | "done";

const URGENCY_STYLE: Record<Urgency, { card: string; label?: string; tone?: string }> = {
  burning: {
    card: "border-wine-400/60 bg-wine-900/20 ring-1 ring-wine-400/30",
    label: "Горит",
    tone: "bg-wine-500 text-white",
  },
  soon: {
    card: "border-sand-400/40 bg-ink-900",
    label: "Скоро заезд",
    tone: "bg-sand-300/20 text-sand-200",
  },
  normal: { card: "border-white/10 bg-ink-900" },
  stale: { card: "border-white/8 bg-ink-900/40 opacity-70", label: "Дата прошла", tone: "bg-white/10 text-muted" },
  done: { card: "border-white/8 bg-ink-900/40 opacity-70" },
};

/** Сколько суток до заезда. null — дат в заявке нет. */
function daysUntil(checkIn: string | null): number | null {
  if (!checkIn) return null;
  const date = new Date(`${checkIn}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((date.getTime() - today.getTime()) / 86_400_000);
}

function urgencyOf(lead: AdminLead): Urgency {
  // Разобранная заявка не срочная, чем бы она ни закончилась.
  if (lead.status !== "new") return "done";
  const days = daysUntil(lead.check_in);
  if (days === null) return "normal";
  if (days < 0) return "stale";
  if (days <= 3) return "burning";
  if (days <= 14) return "soon";
  return "normal";
}

/** Порядок в списке: сверху то, где ещё можно успеть. */
const ORDER: Record<Urgency, number> = { burning: 0, soon: 1, normal: 2, stale: 3, done: 4 };

export function LeadsBoard({
  initialLeads,
  rooms,
}: {
  initialLeads: AdminLead[];
  rooms: AdminRoom[];
}) {
  const [leads, setLeads] = useState(initialLeads);
  const [filter, setFilter] = useState<AdminLead["status"] | "all">("all");
  const [busy, setBusy] = useState<number | null>(null);
  const toast = useToast();

  const roomNames = useMemo(
    () => Object.fromEntries(rooms.map((r) => [r.slug, r.shortName])),
    [rooms],
  );

  const sorted = useMemo(() => {
    const withUrgency = leads.map((lead) => ({ lead, urgency: urgencyOf(lead) }));
    return withUrgency.sort((a, b) => {
      const byUrgency = ORDER[a.urgency] - ORDER[b.urgency];
      if (byUrgency !== 0) return byUrgency;
      // Внутри группы — свежие обращения выше.
      return b.lead.created_at.localeCompare(a.lead.created_at);
    });
  }, [leads]);

  const visible = filter === "all" ? sorted : sorted.filter((x) => x.lead.status === filter);
  const newCount = leads.filter((l) => l.status === "new").length;
  const burningCount = sorted.filter((x) => x.urgency === "burning").length;

  const setStatus = async (lead: AdminLead, status: AdminLead["status"]) => {
    setBusy(lead.id);
    try {
      const updated = await adminSend<AdminLead>(`/leads/${lead.id}`, "PATCH", { status });
      setLeads((prev) => prev.map((l) => (l.id === lead.id ? updated : l)));
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось сохранить", "error");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (lead: AdminLead) => {
    if (!window.confirm(`Удалить заявку «${lead.name}»? Восстановить не получится.`)) return;
    setBusy(lead.id);
    try {
      await adminSend(`/leads/${lead.id}`, "DELETE");
      setLeads((prev) => prev.filter((l) => l.id !== lead.id));
      toast.show("Заявка удалена");
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось удалить", "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <h1 className="font-display text-3xl text-cream md:text-4xl">Заявки</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
        Обращения с формы на сайте от обычных гостей. Брони компаний сюда не
        попадают — они в разделе «Компании», внутри карточки компании.
      </p>
      <p className="mt-2 text-sm text-muted">
        {leads.length === 0
          ? "Заявок пока нет."
          : `Всего ${leads.length}${newCount ? `, из них новых — ${newCount}` : ""}.`}
      </p>

      {burningCount > 0 && (
        <p className="mt-4 rounded-xl border border-wine-400/40 bg-wine-900/25 px-4 py-3 text-sm text-wine-100">
          {burningCount === 1
            ? "Одна заявка с заездом в ближайшие дни ждёт ответа."
            : `Заявок с заездом в ближайшие дни: ${burningCount}. Они наверху списка.`}
        </p>
      )}

      {leads.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-2">
          {(["all", ...LEAD_STATUSES.map((s) => s.value)] as const).map((value) => {
            const label =
              value === "all"
                ? "Все"
                : LEAD_STATUSES.find((s) => s.value === value)?.label ?? value;
            return (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={`rounded-full px-4 py-2 text-sm transition-colors ${
                  filter === value ? "bg-white/10 text-cream" : "text-muted hover:text-cream"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-6 space-y-3">
        {visible.map(({ lead, urgency }) => {
          const status = LEAD_STATUSES.find((s) => s.value === lead.status);
          const look = URGENCY_STYLE[urgency];
          const days = daysUntil(lead.check_in);
          return (
            <article key={lead.id} className={`rounded-2xl border p-5 ${look.card}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="font-display text-lg text-cream">{lead.name}</h2>

                    {look.label && (
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[0.65rem] tracking-wide uppercase ${look.tone}`}
                      >
                        {look.label}
                        {urgency === "burning" && days !== null
                          ? days === 0
                            ? " · сегодня"
                            : days === 1
                              ? " · завтра"
                              : ` · через ${days} дн.`
                          : ""}
                      </span>
                    )}

                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-[0.65rem] tracking-wide uppercase ${
                        status?.tone ?? "border-white/20 text-muted"
                      }`}
                    >
                      {status?.label ?? lead.status}
                    </span>
                    <span className="text-xs text-muted">
                      {dateFormat.format(new Date(lead.created_at))}
                    </span>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
                    <a
                      href={`tel:${lead.phone.replace(/[^\d+]/g, "")}`}
                      className="text-sand-300 underline underline-offset-4"
                    >
                      {lead.phone}
                    </a>
                    <a
                      href={`https://wa.me/${lead.phone.replace(/\D/g, "")}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#25D366] underline underline-offset-4"
                    >
                      WhatsApp
                    </a>
                    {lead.email && (
                      <a
                        href={`mailto:${lead.email}`}
                        className="break-all text-cream/80 underline underline-offset-4"
                      >
                        {lead.email}
                      </a>
                    )}
                  </div>

                  <p className="mt-3 text-sm text-muted">
                    {roomNames[lead.room ?? ""] ?? "Номер не выбран"} ·{" "}
                    {lead.check_in ?? "—"} → {lead.check_out ?? "—"} · гостей:{" "}
                    {lead.adults || "—"}
                  </p>

                  {lead.comment && (
                    <p className="mt-3 rounded-xl border border-white/8 bg-ink-950/50 p-3 text-sm text-cream/80">
                      {lead.comment}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 flex-col items-end gap-2">
                  <select
                    value={lead.status}
                    disabled={busy === lead.id}
                    onChange={(e) => setStatus(lead, e.target.value as AdminLead["status"])}
                    className="rounded-xl border border-white/12 bg-ink-950/60 px-3.5 py-2.5 text-sm text-cream outline-none focus:border-sand-400/60 disabled:opacity-50 [color-scheme:dark]"
                  >
                    {LEAD_STATUSES.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  {/* Удаление для мусора: проверок формы и спама. Настоящую
                      заявку правильнее закрывать статусом — он оставляет след. */}
                  <button
                    type="button"
                    disabled={busy === lead.id}
                    onClick={() => remove(lead)}
                    className="text-xs text-muted underline underline-offset-2 transition-colors hover:text-wine-200 disabled:opacity-50"
                  >
                    удалить
                  </button>
                </div>
              </div>
            </article>
          );
        })}

        {leads.length > 0 && visible.length === 0 && (
          <p className="rounded-2xl border border-white/10 bg-ink-900 p-8 text-center text-sm text-muted">
            В этой категории заявок нет.
          </p>
        )}
      </div>
    </div>
  );
}
