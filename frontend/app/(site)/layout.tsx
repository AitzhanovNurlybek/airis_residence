import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { SmoothScroll } from "@/components/layout/SmoothScroll";
import { FloatingActions } from "@/components/layout/FloatingActions";
import { JsonLd } from "@/components/JsonLd";
import { hotelJsonLd } from "@/lib/seo";
import { getRooms } from "@/lib/rooms";

/** Оболочка публичной части сайта. Админка сюда не попадает. */
export default async function SiteLayout({ children }: LayoutProps<"/">) {
  const rooms = await getRooms();

  return (
    <>
      <JsonLd data={hotelJsonLd(rooms)} />
      <SmoothScroll />
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-100 focus:rounded-full focus:bg-wine-600 focus:px-5 focus:py-3 focus:text-sm"
      >
        Перейти к содержимому
      </a>
      <Header />
      <main id="content" className="flex-1">
        {children}
      </main>
      <Footer rooms={rooms} />
      <FloatingActions />
    </>
  );
}
