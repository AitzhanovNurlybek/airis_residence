import type { Metadata } from "next";

import { Rooms } from "@/components/sections/Rooms";
import { CtaBook } from "@/components/sections/CtaBook";
import { JsonLd } from "@/components/JsonLd";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { priceFrom, formatPrice } from "@/lib/site";
import { getRooms } from "@/lib/rooms";

export const metadata: Metadata = pageMetadata({
  title: `Номера отеля Airis Residence в Алматы — от ${formatPrice(priceFrom)}`,
  description:
    "Пять типов номеров в отеле Airis Residence: Standart Single, Standart, Standart Twin, Comfort и Luxe. Площадь от 16 до 30 м², завтрак включён, цены от 25 000 ₸ за ночь.",
  path: "/nomera",
});

export default async function RoomsPage() {
  const rooms = await getRooms();

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "Номера", path: "/nomera" },
        ])}
      />
      <div className="pt-[calc(var(--header-h)+3.5rem)]">
        <header className="container-page max-w-3xl">
          <p className="eyebrow">Размещение</p>
          <h1 className="mt-4 font-display text-[clamp(2.2rem,5vw,3.6rem)] leading-[1.05] font-semibold text-cream">
            Номера отеля Airis Residence
          </h1>
          <p className="mt-5 text-[1.02rem] leading-relaxed text-muted">
            {rooms.length} типов номеров. В каждом — кондиционер, сейф, мини-бар,
            рабочая зона и собственная ванная комната. Завтрак включён в стоимость
            любого номера.
          </p>
        </header>
        <Rooms rooms={rooms} />
        <CtaBook />
      </div>
    </>
  );
}
