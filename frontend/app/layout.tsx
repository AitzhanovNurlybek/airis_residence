import type { Metadata, Viewport } from "next";
import { Manrope, Playfair_Display } from "next/font/google";
import "./globals.css";

import { BASE_URL } from "@/lib/seo";
import { site } from "@/lib/site";

/**
 * Корневой лейаут — только оболочка документа и шрифты.
 *
 * Шапка, подвал и плавающие кнопки живут в app/(site)/layout.tsx,
 * потому что админке в app/admin они не нужны: там своя навигация.
 */

const display = Playfair_Display({
  subsets: ["latin", "cyrillic"],
  variable: "--font-display",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const sans = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-sans",
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "Airis Residence — отель в центре Алматы | Официальный сайт",
    template: "%s | Airis Residence",
  },
  // Без цены: этот текст статичен, а цены правят в админке — цифра
  // здесь неизбежно разойдётся с сайтом. Цену показывают страницы,
  // которые считают её из базы (см. generateMetadata на главной).
  description: `Airis Residence — отель на ${site.roomsCount} номеров в центре Алматы, ${site.address.street}. Завтрак включён, круглосуточная стойка регистрации. Бронирование на официальном сайте.`,
  keywords: [
    "отель Алматы",
    "гостиница Алматы центр",
    "Airis Residence",
    "забронировать номер Алматы",
    "отель Наурызбай батыра",
    "гостиница с завтраком Алматы",
  ],
  applicationName: site.name,
  authors: [{ name: site.legalName }],
  creator: site.legalName,
  publisher: site.legalName,
  formatDetection: { telephone: true, address: true, email: true },
  alternates: { canonical: BASE_URL },
  openGraph: {
    type: "website",
    locale: site.locale,
    url: BASE_URL,
    siteName: site.name,
    title: "Airis Residence — отель в центре Алматы",
    description:
      `${site.roomsCount} номеров в центре Алматы. Завтрак включён, стойка регистрации 24/7.`,
    images: [{ url: "/og.jpg", width: 1200, height: 630, alt: "Airis Residence, Алматы" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Airis Residence — отель в центре Алматы",
    description: `${site.roomsCount} номеров в центре Алматы. Завтрак включён, стойка 24/7.`,
    images: ["/og.jpg"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
};

export const viewport: Viewport = {
  themeColor: "#1a1417",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

/**
 * Домен хранилища, откуда приходят загруженные фото и видеообзоры.
 * Браузеру полезно установить соединение заранее: пока он читает
 * разметку, рукопожатие с чужим доменом уже идёт.
 */
function mediaOrigin(): string | null {
  const base = process.env.NEXT_PUBLIC_MEDIA_BASE;
  if (!base) return null;
  try {
    return new URL(base).origin;
  } catch {
    return null;
  }
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  const media = mediaOrigin();

  return (
    <html lang="ru" className={`${display.variable} ${sans.variable} antialiased`}>
      {media && (
        <head>
          <link rel="preconnect" href={media} crossOrigin="" />
          <link rel="dns-prefetch" href={media} />
        </head>
      )}
      <body className="flex min-h-dvh flex-col">{children}</body>
    </html>
  );
}
