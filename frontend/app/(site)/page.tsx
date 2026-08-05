import type { Metadata } from "next";

import { Hero } from "@/components/sections/Hero";
import { About } from "@/components/sections/About";
import { Rooms } from "@/components/sections/Rooms";
import { Amenities } from "@/components/sections/Amenities";
import { Gallery } from "@/components/sections/Gallery";
import { Tour3D } from "@/components/sections/Tour3D";
import { Location } from "@/components/sections/Location";
import { Faq } from "@/components/sections/Faq";
import { CtaBook } from "@/components/sections/CtaBook";
import { JsonLd } from "@/components/JsonLd";
import { faqJsonLd, pageMetadata } from "@/lib/seo";
import { faqItems } from "@/lib/faq";
import { getRooms } from "@/lib/rooms";

export const metadata: Metadata = pageMetadata({
  title: "Airis Residence — отель в центре Алматы | Официальный сайт",
  description:
    "Отель Airis Residence в центре Алматы: 36 номеров, завтрак включён, стойка регистрации 24/7. ул. Наурызбай батыра 134/2. Номера от 25 000 ₸ за ночь — бронирование напрямую, без комиссии агрегаторов.",
  path: "/",
});

export default async function HomePage() {
  const rooms = await getRooms();
  const priceFrom = Math.min(...rooms.map((room) => room.price));

  return (
    <>
      <JsonLd data={faqJsonLd(faqItems.map((i) => ({ q: i.q, a: i.a })))} />
      <Hero priceFrom={priceFrom} />
      <About />
      <Rooms rooms={rooms} />
      <Amenities />
      <Gallery />
      <Tour3D />
      <Location />
      <Faq />
      <CtaBook />
    </>
  );
}
