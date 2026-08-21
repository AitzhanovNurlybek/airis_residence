"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Отмена брони.
 *
 * Подтверждение обязательно: строка в таблице узкая, ссылки рядом, а отмена
 * необратима — менеджер уже мог поставить номер в план.
 */
export function CancelBooking({
  bookingId,
  label,
  confirmText,
}: {
  bookingId: number;
  label: string;
  confirmText: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        if (!window.confirm(confirmText)) return;
        setBusy(true);
        const res = await fetch(`/api/corp/bookings/${bookingId}/cancel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "" }),
        }).catch(() => null);
        setBusy(false);
        if (res?.ok) router.refresh();
      }}
      className="text-xs text-wine-600 underline underline-offset-2 disabled:opacity-50"
    >
      {label}
    </button>
  );
}
