"use client";

import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

/* ------------------------------------------------------------------ */
/*  Поля                                                               */
/* ------------------------------------------------------------------ */

export const inputClass =
  "w-full rounded-xl border border-white/12 bg-ink-950/60 px-4 py-3 text-[0.95rem] text-cream outline-none transition-colors placeholder:text-muted/60 focus:border-sand-400/60 disabled:opacity-50 [color-scheme:dark]";

export const labelClass =
  "mb-2 block text-[0.68rem] font-medium tracking-[0.14em] text-sand-400 uppercase";

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className={labelClass}>{label}</label>
      {children}
      {hint && <p className="mt-1.5 text-xs leading-relaxed text-muted">{hint}</p>}
    </div>
  );
}

export function AdminButton({
  variant = "primary",
  className = "",
  children,
  ...rest
}: {
  variant?: "primary" | "secondary" | "danger" | "quiet";
  className?: string;
  children: ReactNode;
} & React.ComponentProps<"button">) {
  const styles = {
    primary:
      "bg-linear-to-b from-wine-500 to-wine-700 text-white hover:from-wine-400 hover:to-wine-600",
    secondary: "border border-white/15 text-cream hover:border-sand-400/50 hover:bg-white/5",
    danger: "border border-wine-400/40 text-wine-200 hover:bg-wine-900/40",
    quiet: "text-muted hover:text-cream",
  }[variant];

  return (
    <button
      className={`inline-flex h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-medium transition-[transform,background-color,box-shadow,border-color,color] duration-200 ease-airis active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 ${styles} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Всплывающие уведомления                                            */
/* ------------------------------------------------------------------ */

type Toast = { id: number; text: string; kind: "ok" | "error" };
type ToastApi = { show: (text: string, kind?: "ok" | "error") => void };

const ToastContext = createContext<ToastApi>({ show: () => {} });

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const show = useCallback((text: string, kind: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, text, kind }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-6 z-100 flex flex-col items-center gap-2 px-4">
        <AnimatePresence>
          {items.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 24, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className={`pointer-events-auto max-w-md rounded-full px-5 py-3 text-sm shadow-deep backdrop-blur-xl ${
                toast.kind === "ok"
                  ? "border border-sand-400/30 bg-ink-800/95 text-sand-100"
                  : "border border-wine-400/45 bg-wine-900/90 text-wine-50"
              }`}
            >
              {toast.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

/* ------------------------------------------------------------------ */
/*  Индикатор «есть несохранённые правки»                              */
/* ------------------------------------------------------------------ */

export function SaveBar({
  dirty,
  saving,
  onSave,
  onReset,
}: {
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  return (
    <AnimatePresence>
      {dirty && (
        <motion.div
          initial={{ y: 90, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 90, opacity: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-x-0 bottom-0 z-50 border-t border-white/10 bg-ink-900/95 backdrop-blur-xl"
        >
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-4">
            <span className="text-sm text-sand-200">Есть несохранённые изменения</span>
            <div className="flex gap-2">
              <AdminButton variant="quiet" onClick={onReset} disabled={saving}>
                Отменить
              </AdminButton>
              <AdminButton onClick={onSave} disabled={saving}>
                {saving ? "Сохраняем…" : "Сохранить"}
              </AdminButton>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
