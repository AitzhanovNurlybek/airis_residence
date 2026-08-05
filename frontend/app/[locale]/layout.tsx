import type { Metadata, Viewport } from "next";
import { notFound } from "next/navigation";

import "../globals.css";
import { fontClass } from "../fonts";

import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { SmoothScroll } from "@/components/layout/SmoothScroll";
import { FloatingActions } from "@/components/layout/FloatingActions";
import { JsonLd } from "@/components/JsonLd";
import { hotelJsonLd, BASE_URL, alternates } from "@/lib/seo";
import { getRooms } from "@/lib/rooms";
import { site } from "@/lib/site";
import { getDictionary, isLocale, localeMeta, locales, t } from "@/lib/i18n";
import { I18nProvider } from "@/components/i18n/I18nProvider";

/**
 * Корневой лейаут публичного сайта.
 *
 * Их в проекте два: этот и app/admin/layout.tsx. Так админка не тянет
 * на себя шапку, подвал и языковую схему сайта — у неё свои задачи.
 */

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata(props: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await props.params;
  if (!isLocale(locale)) return {};
  const d = getDictionary(locale);

  return {
    metadataBase: new URL(BASE_URL),
    title: {
      default: d.meta.homeTitle,
      template: `%s | ${site.name}`,
    },
    description: t(d.meta.homeDescription, { count: site.roomsCount, price: "25 000 ₸" }),
    applicationName: site.name,
    authors: [{ name: site.legalName }],
    creator: site.legalName,
    publisher: site.legalName,
    formatDetection: { telephone: true, address: true, email: true },
    alternates: alternates(locale, "/"),
    openGraph: {
      type: "website",
      locale: localeMeta[locale].htmlLang,
      siteName: site.name,
      title: d.meta.homeTitle,
      images: [{ url: "/og.jpg", width: 1200, height: 630, alt: site.name }],
    },
    twitter: { card: "summary_large_image", images: ["/og.jpg"] },
    robots: {
      index: true,
      follow: true,
      googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
    },
  };
}

export const viewport: Viewport = {
  themeColor: "#0a0809",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default async function LocaleLayout(props: LayoutProps<"/[locale]">) {
  const { locale } = await props.params;
  if (!isLocale(locale)) notFound();

  const d = getDictionary(locale);
  const rooms = await getRooms(locale);

  return (
    <html lang={localeMeta[locale].htmlLang} className={`${fontClass} antialiased`}>
      <body className="flex min-h-dvh flex-col">
        <I18nProvider locale={locale} dict={d}>
          <JsonLd data={hotelJsonLd(rooms, locale)} />
          <SmoothScroll />
          <a
            href="#content"
            className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-100 focus:rounded-full focus:bg-wine-600 focus:px-5 focus:py-3 focus:text-sm"
          >
            {d.nav.toContent}
          </a>
          <Header locale={locale} dict={d} />
          <main id="content" className="flex-1">
            {props.children}
          </main>
          <Footer locale={locale} dict={d} rooms={rooms} />
          <FloatingActions locale={locale} dict={d} />
        </I18nProvider>
      </body>
    </html>
  );
}
