import type { Metadata } from "next";

import { formatPrice, site } from "@/lib/site";

import { Hero } from "@/components/sections/Hero";
import { About } from "@/components/sections/About";
import { EventsNearby } from "@/components/sections/EventsNearby";
import { Rooms } from "@/components/sections/Rooms";
import { Amenities } from "@/components/sections/Amenities";
import { Gallery } from "@/components/sections/Gallery";
import { Tour3D } from "@/components/sections/Tour3D";
import { VideoShowcase } from "@/components/sections/VideoShowcase";
import { Location } from "@/components/sections/Location";
import { Faq } from "@/components/sections/Faq";
import { Corporate } from "@/components/sections/Corporate";
import { CtaBook } from "@/components/sections/CtaBook";
import { JsonLd } from "@/components/JsonLd";
import { faqJsonLd, pageMetadata } from "@/lib/seo";
import { faqItems } from "@/lib/faq";
import { getPriceFrom, getRooms } from "@/lib/rooms";

// Цену берём из базы, а не из запасного списка в коде: её меняют
// в админке, и описание в выдаче Google обязано совпадать с сайтом.
export async function generateMetadata(): Promise<Metadata> {
  return pageMetadata({
    title: "Airis Residence, Алматы - Официальный сайт",
    description: `Отель Airis Residence в центре Алматы: ${site.roomsCount} номеров, завтрак включён, стойка регистрации 24/7. ${site.address.street}. Номера от ${formatPrice(await getPriceFrom())} за ночь — бронирование напрямую, без комиссии агрегаторов.`,
    path: "/",
  });
}

export default async function HomePage() {
  const rooms = await getRooms();
  const priceFrom = Math.min(...rooms.map((room) => room.price));

  return (
    <>
      <JsonLd data={faqJsonLd(faqItems.map((i) => ({ q: i.q, a: i.a })))} />
      <Hero priceFrom={priceFrom} />
      {/* Сразу под первым экраном: туриста, летящего на концерт или матч,
          цепляет именно это, а рассказ об отеле он читает уже потом. */}
      <EventsNearby />
      <About />
      <Rooms rooms={rooms} />
      <Amenities />
      <Gallery />
      <VideoShowcase />
      <Tour3D />
      <Location />
      <Faq />
      <Corporate />
      <CtaBook />
    </>
  );
}
