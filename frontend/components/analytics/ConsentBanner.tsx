"use client";

import { useEffect, useState } from "react";

const KEY = "airis-consent";

/** Часовые пояса «Europe/…», где согласие не требуется: Россия, Беларусь, Турция и т. п. */
const NOT_CONSENT_ZONES = new Set([
  "Europe/Moscow", "Europe/Minsk", "Europe/Kaliningrad", "Europe/Samara", "Europe/Volgograd",
  "Europe/Kirov", "Europe/Astrakhan", "Europe/Saratov", "Europe/Ulyanovsk", "Europe/Simferopol",
  "Europe/Istanbul",
]);

type Gtag = (...args: unknown[]) => void;

function gtag(...args: unknown[]) {
  const fn = (window as unknown as { gtag?: Gtag }).gtag;
  if (fn) fn(...args);
}

/**
 * Баннер согласия на cookie — только тем, кто, судя по часовому поясу, из
 * Европы. Гостям из Казахстана он не нужен и только мешал бы забронировать.
 * Ответ запоминается: второй раз баннер не появляется.
 */
export function ConsentBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(KEY)) return;
    } catch {
      return;
    }
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    if (zone.startsWith("Europe/") && !NOT_CONSENT_ZONES.has(zone)) setShow(true);
  }, []);

  function answer(granted: boolean) {
    try {
      localStorage.setItem(KEY, granted ? "granted" : "denied");
    } catch {
      // без хранилища баннер просто появится снова
    }
    if (granted) {
      gtag("consent", "update", {
        ad_storage: "granted",
        ad_user_data: "granted",
        ad_personalization: "granted",
        analytics_storage: "granted",
      });
    }
    setShow(false);
  }

  if (!show) return null;
  return (
    <div
      role="dialog"
      aria-label="Cookie"
      className="fixed inset-x-3 bottom-3 z-[60] mx-auto max-w-xl rounded-card border border-white/10 bg-ink-900/95 p-4 text-sm text-cream/85 shadow-2xl backdrop-blur md:bottom-5 md:p-5"
    >
      <p>
        Мы используем cookie, чтобы понимать, как гости находят сайт, и показывать
        им актуальные предложения.{" "}
        <a href="/politika-konfidencialnosti" className="underline underline-offset-2 hover:text-sand-300">
          Подробнее
        </a>
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => answer(true)}
          className="rounded-full bg-sand-400 px-4 py-2 font-medium text-ink-950 hover:bg-sand-300"
        >
          Согласен
        </button>
        <button
          type="button"
          onClick={() => answer(false)}
          className="rounded-full border border-white/20 px-4 py-2 hover:border-white/40"
        >
          Только необходимые
        </button>
      </div>
    </div>
  );
}
