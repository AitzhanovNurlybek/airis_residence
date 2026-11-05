import Script from "next/script";

import { ConsentBanner } from "./ConsentBanner";
import { ClickTracking } from "./ClickTracking";
import type { Lang } from "@/lib/routes";

/**
 * Google Analytics 4 — с режимом согласия (Consent Mode v2).
 *
 * Зачем режим согласия. Отель запускает рекламу на Европу (2026-11-04), а для
 * посетителей из ЕЭЗ, Великобритании и Швейцарии Google требует согласие на
 * cookie: без него реклама на этих людей работает хуже, а счётчик собирает
 * данные без разрешения. Поэтому для этих стран cookie выключены, пока гость
 * не нажал «Согласен» в баннере; Google в это время получает обезличенные
 * сигналы и сам досчитывает статистику. Для остальных стран — как обычно.
 *
 * ID не секрет: он и так виден в коде любой страницы.
 */
export const GA_ID = "G-H5PKFPNZS6";

/** Страны, где без согласия cookie выключены: ЕЭЗ + Великобритания + Швейцария. */
const CONSENT_REGIONS = [
  "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
  "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
  "IS", "LI", "NO", "GB", "CH",
];

const init = `
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
window.gtag = gtag;
gtag('consent', 'default', {
  ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
  analytics_storage: 'denied', wait_for_update: 500,
  region: ${JSON.stringify(CONSENT_REGIONS)}
});
gtag('consent', 'default', {
  ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'granted',
  analytics_storage: 'granted'
});
try {
  if (localStorage.getItem('airis-consent') === 'granted') {
    gtag('consent', 'update', {
      ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'granted',
      analytics_storage: 'granted'
    });
  }
} catch (e) {}
gtag('set', 'ads_data_redaction', true);
gtag('set', 'url_passthrough', true);
gtag('js', new Date());
gtag('config', '${GA_ID}');
`;

export function Analytics({ lang = "ru" }: { lang?: Lang }) {
  if (process.env.NODE_ENV !== "production") return null;
  return (
    <>
      <Script id="ga-init" strategy="afterInteractive">
        {init}
      </Script>
      <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
      <ClickTracking />
      <ConsentBanner lang={lang} />
    </>
  );
}
