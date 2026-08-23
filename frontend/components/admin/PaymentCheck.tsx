"use client";

import { useRef, useState } from "react";

import { AdminButton } from "@/components/admin/ui";
import { adminUpload } from "@/lib/adminClient";

/**
 * Проверка присланного чека.
 *
 * Что здесь важно понимать про сам замысел: документ — это заявление гостя об
 * оплате, а не сама оплата. Единственное настоящее подтверждение — деньги на
 * счёте. Поэтому страница нигде не говорит «оплачено подтверждено»: она
 * говорит, что бумага не противоречит брони, и просит сверить с выпиской.
 *
 * Проверок три, и они разного веса. Получатель — единственная надёжная:
 * подделать вид документа несложно, а вот платёж в пользу чужой компании
 * отелю не поможет ничем. Следы правки и сумма прописью ловят топорные
 * подделки. Совпадение с бронью — про деньги, а не про подлинность.
 */

type Recipient = { status: "ok" | "mismatch" | "unknown"; note: string };
type Doc = {
  isPayment: boolean;
  payer: string;
  payerBin: string;
  payee: string;
  payeeBin: string;
  payeeAccount: string;
  amount: number;
  amountInWords: string;
  currency: string;
  paidAt: string;
  purpose: string;
  reference: string;
  bank: string;
  docNumber: string;
  statusWords: string;
  redFlags: string[];
  looksEdited: boolean;
};
type Result = {
  verdict: "applied" | "review" | "duplicate" | "rejected";
  reason: string;
  bookingRef: string;
  appliedAmount: number;
  recipient: Recipient;
  doc: Doc;
};

const money = new Intl.NumberFormat("ru-RU");

const VERDICT: Record<Result["verdict"], { title: string; tone: string }> = {
  applied: {
    title: "Оплата отмечена",
    tone: "border-emerald-400/40 bg-emerald-500/10 text-emerald-100",
  },
  duplicate: {
    title: "Этот чек уже присылали",
    tone: "border-sand-400/40 bg-sand-400/10 text-sand-100",
  },
  review: {
    title: "Нужен человек",
    tone: "border-sand-400/40 bg-sand-400/10 text-sand-100",
  },
  rejected: {
    title: "Отклонено",
    tone: "border-wine-400/40 bg-wine-600/15 text-wine-100",
  },
};

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-xs tracking-wide text-muted uppercase">{label}</div>
      <div className="mt-1 text-sm text-cream/90">{value}</div>
    </div>
  );
}

export function PaymentCheck({ onApplied }: { onApplied?: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [name, setName] = useState("");
  const picker = useRef<HTMLInputElement>(null);

  async function send(file: File) {
    setBusy(true);
    setError("");
    setResult(null);
    setName(file.name);
    try {
      const data = await adminUpload<Result>("/local/payment", [file]);
      setResult(data);
      if (data.verdict === "applied") onApplied?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось разобрать документ");
    } finally {
      setBusy(false);
      if (picker.current) picker.current.value = "";
    }
  }

  const doc = result?.doc;
  const recipient = result?.recipient;

  return (
    <div>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files?.[0];
          if (file) void send(file);
        }}
        className="rounded-2xl border border-dashed border-white/15 bg-ink-900/50 p-8 text-center"
      >
        <p className="text-sm text-cream/85">
          Перетащите сюда чек или платёжное поручение
        </p>
        <p className="mt-1 text-xs text-muted">PDF, PNG или JPG, до 8 МБ</p>
        <input
          ref={picker}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void send(file);
          }}
        />
        <AdminButton
          type="button"
          variant="secondary"
          className="mt-5"
          disabled={busy}
          onClick={() => picker.current?.click()}
        >
          {busy ? "Читаю документ…" : "Выбрать файл"}
        </AdminButton>
        {busy && name && (
          <p className="mt-3 text-xs text-muted">{name} — это занимает несколько секунд</p>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-xl bg-wine-600/15 px-4 py-3 text-sm text-wine-200">
          {error}
        </p>
      )}

      {result && doc && recipient && (
        <div className="mt-5 grid gap-4">
          <div className={`rounded-2xl border px-5 py-4 ${VERDICT[result.verdict].tone}`}>
            <div className="font-display text-lg">{VERDICT[result.verdict].title}</div>
            <p className="mt-1 text-sm opacity-90">{result.reason}</p>
            {result.bookingRef && (
              <p className="mt-2 text-sm opacity-90">
                Бронь {result.bookingRef}
                {result.appliedAmount > 0 && ` · засчитано ${money.format(result.appliedAmount)} ₸`}
              </p>
            )}
          </div>

          {/* Три проверки списком: видно, какая прошла, а какая нет. */}
          <div className="grid gap-2">
            <Check
              ok={recipient.status === "ok"}
              unknown={recipient.status === "unknown"}
              title="Деньги отелю"
              note={recipient.note}
            />
            {/* Замечания модели показываем, но крестик за них не ставим:
                оплату они не блокируют, а значок должен совпадать с тем, что
                система на самом деле сделала. Блокирует только заявленная
                правка изображения. */}
            <Check
              ok={!doc.looksEdited && doc.redFlags.length === 0}
              unknown={!doc.looksEdited && doc.redFlags.length > 0}
              title="Документ без следов правки"
              note={
                doc.looksEdited
                  ? `Похоже на отредактированное изображение. ${doc.redFlags.join("; ")}`.trim()
                  : doc.redFlags.length
                    ? `Замечания, которые не мешают засчитать: ${doc.redFlags.join("; ")}`
                    : "Ничего подозрительного не видно"
              }
            />
            <Check
              ok={result.verdict === "applied"}
              unknown={result.verdict === "duplicate"}
              title="Сходится с бронью"
              note={result.reason}
            />
          </div>

          <div className="rounded-2xl border border-white/10 bg-ink-900/50 p-5">
            <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
              <Row label="Плательщик" value={doc.payer + (doc.payerBin ? ` · БИН ${doc.payerBin}` : "")} />
              <Row label="Получатель" value={doc.payee + (doc.payeeBin ? ` · БИН ${doc.payeeBin}` : "")} />
              <Row
                label="Сумма"
                value={doc.amount ? `${money.format(doc.amount)} ${doc.currency}` : ""}
              />
              <Row label="Сумма прописью" value={doc.amountInWords} />
              <Row label="Дата платежа" value={doc.paidAt} />
              <Row label="Банк" value={doc.bank} />
              <Row label="Номер документа" value={doc.docNumber} />
              <Row label="Статус в документе" value={doc.statusWords} />
              <div className="md:col-span-2">
                <Row label="Назначение платежа" value={doc.purpose} />
              </div>
            </div>
          </div>

          <p className="text-xs leading-relaxed text-muted">
            Чек — это заявление гостя об оплате, а не сама оплата. Даже когда все проверки
            прошли, деньги нужно увидеть в выписке: документ можно подделать, поступление на
            счёт — нет.
          </p>
        </div>
      )}
    </div>
  );
}

function Check({
  ok,
  unknown = false,
  title,
  note,
}: {
  ok: boolean;
  unknown?: boolean;
  title: string;
  note: string;
}) {
  const mark = ok ? "✓" : unknown ? "?" : "✕";
  const tone = ok ? "text-emerald-300" : unknown ? "text-sand-300" : "text-wine-300";
  return (
    <div className="flex items-start gap-3 rounded-xl border border-white/10 bg-ink-900/40 px-4 py-3">
      <span className={`mt-0.5 font-display text-lg leading-none ${tone}`}>{mark}</span>
      <div>
        <div className="text-sm text-cream">{title}</div>
        <div className="mt-0.5 text-xs text-muted">{note}</div>
      </div>
    </div>
  );
}
