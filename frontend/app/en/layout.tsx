import type { Metadata } from "next";

import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { SmoothScroll } from "@/components/layout/SmoothScroll";
import { FloatingActions } from "@/components/layout/FloatingActions";
import { JsonLd } from "@/components/JsonLd";
import { Analytics } from "@/components/analytics/Analytics";
import { hotelJsonLd } from "@/lib/seo";
import { getRooms } from "@/lib/rooms";
import { site } from "@/lib/site";

/**
 * Оболочка английских страниц (/en/...).
 *
 * Корневой лейаут один на весь сайт и пишет <html lang="ru">: узнать
 * адрес страницы он не может, а два корневых лейаута потянули бы за собой
 * перестройку админки, кабинета и общей страницы 404. Поэтому язык
 * документа здесь меняет короткий скрипт до отрисовки. Google язык
 * страницы определяет по тексту и по hreflang, атрибут нужен экранным
 * чтецам и Bing.
 */
export const metadata: Metadata = {
  title: {
    default: "Airis Residence — hotel in Almaty city centre | Official website",
    template: "%s | Airis Residence",
  },
  description: `Airis Residence is a ${site.roomsCount}-room hotel in Almaty city centre. Breakfast included, 24/7 front desk, English-speaking staff. Book direct on the official website.`,
  keywords: [
    "Almaty hotel",
    "hotel in Almaty city centre",
    "where to stay in Almaty",
    "Airis Residence",
    "Almaty hotel with breakfast",
  ],
};

export default async function EnLayout({ children }: LayoutProps<"/en">) {
  const rooms = await getRooms();

  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: 'document.documentElement.lang="en"' }} />
      <JsonLd data={hotelJsonLd(rooms, "en")} />
      <SmoothScroll />
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-100 focus:rounded-full focus:bg-wine-600 focus:px-5 focus:py-3 focus:text-sm"
      >
        Skip to content
      </a>
      <Header lang="en" />
      <main id="content" className="flex-1" lang="en">
        {children}
      </main>
      <Footer rooms={rooms} lang="en" />
      <FloatingActions lang="en" />
      <Analytics lang="en" />
    </>
  );
}
