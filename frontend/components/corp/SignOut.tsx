"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Выход. Кнопка, а не ссылка: куку гасит DELETE-запрос, а GET по ссылке
 * может выполнить браузерный предзагрузчик — и человек окажется разлогинен,
 * просто наведя курсор.
 */
export function SignOut({ label }: { label: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        await fetch("/api/corp/login", { method: "DELETE" }).catch(() => null);
        router.replace("/corp/login");
        router.refresh();
      }}
      className="text-sm text-cream/85 transition-colors hover:text-cream disabled:opacity-50"
    >
      {label}
    </button>
  );
}
