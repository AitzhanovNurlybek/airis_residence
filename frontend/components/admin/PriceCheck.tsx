"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminButton } from "@/components/admin/ui";
import { adminGet, adminSend } from "@/lib/adminClient";

/**
 * Цена на сайте против цены, по которой номер продаётся.
 *
 * Цена живёт в двух местах: здесь, в админке, и в тарифах Exely. Между ними
 * нет никакой связи, и разойтись они могут молча — что и произошло. Причём
 * разошлись в сторону, о которой никто не пожалуется: сайт показывает дороже
 * настоящего. Гость не приходит ругаться, он просто не открывает форму.
 *
 * Блок намеренно не прячется, когда всё сходится: тогда его перестают
 * замечать, и первое расхождение проходит мимо глаз. Сошлось — зелёная
 * строчка, разошлось — жёлтая таблица.
 */

type Row = {
  roomSlug: string;
  roomName: string;
  sitePrice: number;
  sellingFrom: number | null;
  rateName: string;
  difference: number | null;
  onSale: boolean;
};
type Check = { checkedOn: string; reachable: boolean; rooms: Row[]; mismatched: number };

const money = new Intl.NumberFormat("ru-RU");

type Synced = { roomName: string; before: number; after: number };

export function PriceCheck() {
  const [data, setData] = useState<Check | null>(null);
  const [loadError, setLoadError] = useState("");
  const [syncError, setSyncError] = useState("");
  const [busy, setBusy] = useState(false);
  const [synced, setSynced] = useState<Synced[] | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await adminGet<Check>("/local/prices"));
      setLoadError("");
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Не удалось свериться");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function sync() {
    setBusy(true);
    setSyncError("");
    setSynced(null);
    try {
      const result = await adminSend<{ checkedOn: string; changed: Synced[] }>(
        "/local/prices/sync",
        "POST",
        {},
      );
      setSynced(result.changed);
      await load();
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : "Не удалось подтянуть цены");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return null;
  if (!data) return null;

  if (!data.reachable) {
    return (
      <div className="mb-6 rounded-2xl border border-white/10 bg-ink-900/50 px-5 py-4 text-sm text-muted">
        Система бронирования не ответила — сверить цены сайта с настоящими не вышло.
      </div>
    );
  }

  const bad = data.rooms.filter((r) => r.difference);

  if (!bad.length) {
    return (
      <div className="mb-6 rounded-2xl border border-emerald-400/30 bg-emerald-500/8 px-5 py-3.5 text-sm text-emerald-100/90">
        Цены на сайте совпадают с тем, по чему номера продаются в системе бронирования.
        {synced && synced.length > 0 && (
          <span className="ml-2 text-emerald-100/70">
            Только что подтянул: {synced.map((s) => s.roomName).join(", ")}.
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="mb-6 rounded-2xl border border-sand-400/40 bg-sand-400/8 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-display text-lg text-sand-100">
            Цены на сайте расходятся с системой бронирования
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-sand-100/80">
            Гость видит на странице одно число, а в форме брони — другое. Проверено на{" "}
            {data.checkedOn}.
          </p>
        </div>
        <AdminButton type="button" variant="secondary" disabled={busy} onClick={() => void sync()}>
          {busy ? "Подтягиваю…" : "Подтянуть цены из Exely"}
        </AdminButton>
      </div>

      {syncError && (
        <p role="alert" className="mt-3 rounded-xl bg-wine-600/15 px-4 py-2.5 text-sm text-wine-200">
          {syncError}
        </p>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="text-xs tracking-wide text-sand-100/60 uppercase">
              <th className="py-2 text-left font-normal">Номер</th>
              <th className="py-2 text-right font-normal">На сайте</th>
              <th className="py-2 text-right font-normal">Продаётся от</th>
              <th className="py-2 pl-6 text-left font-normal">Тариф</th>
            </tr>
          </thead>
          <tbody>
            {bad.map((row) => (
              <tr key={row.roomSlug} className="border-t border-sand-400/15">
                <td className="py-2.5 text-cream">{row.roomName}</td>
                <td className="py-2.5 text-right tabular-nums text-cream">
                  {money.format(row.sitePrice)} ₸
                </td>
                <td className="py-2.5 text-right tabular-nums text-sand-200">
                  {money.format(row.sellingFrom ?? 0)} ₸
                  <span className="ml-2 text-xs text-sand-100/60">
                    {row.difference && row.difference > 0
                      ? `дешевле на ${money.format(row.difference)}`
                      : `дороже на ${money.format(Math.abs(row.difference ?? 0))}`}
                  </span>
                </td>
                <td className="py-2.5 pl-6 text-sand-100/70">{row.rateName || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs leading-relaxed text-sand-100/65">
        Цену меняют в двух местах, и они не связаны: здесь — то, что видно на страницах
        сайта, в Exely — то, по чему гость реально бронирует. Настоящая цена в Exely; здешнюю
        стоит подтянуть к ней, иначе часть гостей уходит, не открыв форму. Кнопка выше
        переносит число один в один — нажимайте, когда сами видите, что тарифы в Exely
        устоялись, а не сразу: пока их там перенастраивают, подтянется сегодняшний
        беспорядок.
      </p>
    </div>
  );
}
