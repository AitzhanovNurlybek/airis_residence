import type { Metadata } from "next";

import { site } from "@/lib/site";
import { faqItemsEn, formatPriceEn, roomEn } from "@/lib/en";

import { Hero } from "@/components/sections/Hero";
import { About } from "@/components/sections/About";
import { EventsNearby } from "@/components/sections/EventsNearby";
import { Rooms } from "@/components/sections/Rooms";
import { ReviewsEn } from "@/components/sections/Reviews";
import { Amenities } from "@/components/sections/Amenities";
import { Gallery } from "@/components/sections/Gallery";
import { VideoShowcase } from "@/components/sections/VideoShowcase";
import { Location } from "@/components/sections/Location";
import { Faq } from "@/components/sections/Faq";
import { CtaBook } from "@/components/sections/CtaBook";
import { GuideTeaser } from "@/components/content/GuideTeaser";
import { JsonLd } from "@/components/JsonLd";
import { faqJsonLd, pageMetadata } from "@/lib/seo";
import { getPriceFrom, getRooms } from "@/lib/rooms";

export async function generateMetadata(): Promise<Metadata> {
  return pageMetadata({
    title: "Airis Residence, Almaty — Official website",
    description: `${site.roomsCount} rooms in Almaty city centre, 800 m from Abay Avenue. Breakfast included, 24/7 front desk, English-speaking staff. From ${formatPriceEn(await getPriceFrom())} per night — book direct, no booking-site markup.`,
    path: "/en",
  });
}

/**
 * Главная по-английски. Порядок блоков тот же, что у русской (см.
 * app/(site)/page.tsx), без двух: корпоративного блока — договоры и счета
 * на юрлицо нужны компаниям Казахстана, а не туристу из Европы, — и
 * 3D-тура, которого пока нет. Вместо них — путеводитель по городу: его
 * иностранцы ищут до поездки.
 */
export default async function HomePageEn() {
  const rooms = (await getRooms()).map(roomEn);
  const priceFrom = Math.min(...rooms.map((room) => room.price));

  return (
    <>
      <JsonLd data={faqJsonLd(faqItemsEn.map((i) => ({ q: i.q, a: i.a })))} />
      <Hero priceFrom={priceFrom} lang="en" />
      <Rooms rooms={rooms} lang="en" />
      <About lang="en" />
      <Gallery lang="en" />
      <VideoShowcase lang="en" />
      <Amenities lang="en" />
      <Location withEvents lang="en" />
      <EventsNearby lang="en" />
      <GuideTeaser lang="en" />
      <Faq lang="en" />
      <ReviewsEn />
      <CtaBook lang="en" />
    </>
  );
}
