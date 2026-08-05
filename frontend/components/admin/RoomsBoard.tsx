"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { adminSend, AdminError } from "@/lib/adminClient";
import type { AdminRoom } from "@/lib/adminTypes";
import { formatPrice } from "@/lib/site";
import { AdminButton, useToast } from "@/components/admin/ui";
import { AdminThumb } from "@/components/admin/AdminThumb";

/**
 * Главный экран: список номеров.
 *
 * Цену можно поправить прямо здесь, не заходя в карточку, — это то,
 * что администратор делает чаще всего. Остальное (тексты, фото) —
 * на отдельной странице номера.
 */
export function RoomsBoard({ initialRooms }: { initialRooms: AdminRoom[] }) {
  const [rooms, setRooms] = useState(initialRooms);
  const [busy, setBusy] = useState<string | null>(null);
  const toast = useToast();
  const router = useRouter();

  const patch = async (slug: string, data: Partial<AdminRoom>, message: string) => {
    setBusy(slug);
    try {
      const updated = await adminSend<AdminRoom>(`/rooms/${slug}`, "PATCH", data);
      setRooms((prev) => prev.map((r) => (r.slug === slug ? updated : r)));
      toast.show(message);
      router.refresh();
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось сохранить", "error");
    } finally {
      setBusy(null);
    }
  };

  const move = async (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= rooms.length) return;

    const next = [...rooms];
    [next[index], next[target]] = [next[target], next[index]];
    setRooms(next);

    setBusy("order");
    try {
      await adminSend("/rooms/reorder", "POST", next.map((r) => r.slug));
      toast.show("Порядок номеров обновлён");
      router.refresh();
    } catch {
      setRooms(rooms);
      toast.show("Не удалось изменить порядок", "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-cream md:text-4xl">Номера</h1>
          <p className="mt-2 text-sm text-muted">
            Цену можно изменить прямо в списке. Фотографии и описание — внутри номера.
          </p>
        </div>
        <Link href="/admin/nomera/novyi">
          <AdminButton variant="secondary">+ Добавить номер</AdminButton>
        </Link>
      </div>

      <div className="mt-8 space-y-3">
        {rooms.length === 0 && (
          <p className="rounded-2xl border border-white/10 bg-ink-900 p-8 text-center text-sm text-muted">
            Номеров пока нет. Нажмите «Добавить номер».
          </p>
        )}

        {rooms.map((room, index) => (
          <div
            key={room.slug}
            className={`rounded-2xl border border-white/10 bg-ink-900 p-4 transition-opacity md:p-5 ${
              room.isPublished ? "" : "opacity-60"
            }`}
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-center">
              <AdminThumb src={room.images[0]} alt={room.shortName} className="w-full md:w-28" />

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Link
                    href={`/admin/nomera/${room.slug}`}
                    className="font-display text-xl text-cream transition-colors hover:text-sand-300"
                  >
                    {room.shortName}
                  </Link>
                  {!room.isPublished && (
                    <span className="rounded-full border border-white/20 px-2.5 py-0.5 text-[0.65rem] tracking-wide text-muted uppercase">
                      скрыт
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm text-muted">
                  {room.area || "площадь не указана"} · до {room.capacity} гостей ·{" "}
                  {room.images.length} фото
                </p>
              </div>

              <PriceInput
                value={room.price}
                disabled={busy === room.slug}
                onSave={(price) =>
                  patch(room.slug, { price }, `Цена ${room.shortName}: ${formatPrice(price)}`)
                }
              />

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  aria-label="Поднять выше"
                  disabled={index === 0 || busy === "order"}
                  onClick={() => move(index, -1)}
                  className="grid size-9 place-items-center rounded-lg border border-white/12 text-muted transition-colors hover:text-cream disabled:opacity-30"
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label="Опустить ниже"
                  disabled={index === rooms.length - 1 || busy === "order"}
                  onClick={() => move(index, 1)}
                  className="grid size-9 place-items-center rounded-lg border border-white/12 text-muted transition-colors hover:text-cream disabled:opacity-30"
                >
                  ↓
                </button>

                <button
                  type="button"
                  disabled={busy === room.slug}
                  onClick={() =>
                    patch(
                      room.slug,
                      { isPublished: !room.isPublished },
                      room.isPublished
                        ? `${room.shortName} скрыт с сайта`
                        : `${room.shortName} опубликован`,
                    )
                  }
                  className="ml-1 rounded-full border border-white/12 px-3.5 py-2 text-xs text-muted transition-colors hover:border-sand-400/50 hover:text-cream disabled:opacity-40"
                >
                  {room.isPublished ? "Скрыть" : "Показать"}
                </button>

                <Link
                  href={`/admin/nomera/${room.slug}`}
                  className="rounded-full bg-white/8 px-4 py-2 text-xs text-cream transition-colors hover:bg-white/14"
                >
                  Изменить
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Цена сохраняется по Enter или когда поле теряет фокус. */
function PriceInput({
  value,
  disabled,
  onSave,
}: {
  value: number;
  disabled: boolean;
  onSave: (price: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  const changed = Number(draft) !== value && draft.trim() !== "";

  const commit = () => {
    const price = Number(draft);
    if (!Number.isFinite(price) || price < 0) {
      setDraft(String(value));
      return;
    }
    if (price !== value) onSave(price);
  };

  return (
    <div className="shrink-0 md:w-44">
      <label className="mb-1 block text-[0.62rem] tracking-[0.14em] text-sand-400 uppercase">
        цена за ночь, ₸
      </label>
      <div className="relative">
        <input
          type="number"
          inputMode="numeric"
          min={0}
          step={500}
          value={draft}
          disabled={disabled}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            if (e.key === "Escape") setDraft(String(value));
          }}
          className={`w-full rounded-xl border bg-ink-950/60 px-3.5 py-2.5 text-[0.95rem] tabular-nums text-cream outline-none transition-colors disabled:opacity-50 ${
            changed ? "border-sand-400/70" : "border-white/12 focus:border-sand-400/60"
          }`}
        />
        {changed && (
          <span className="absolute top-1/2 right-3 -translate-y-1/2 text-[0.62rem] text-sand-400">
            Enter
          </span>
        )}
      </div>
    </div>
  );
}
