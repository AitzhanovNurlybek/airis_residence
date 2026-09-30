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
import { rooms as roomsWord } from "@/lib/plural";

// Цену берём из базы, а не из запасного списка в коде: её меняют
// в админке, и описание в выдаче Google обязано совпадать с сайтом.
export async function generateMetadata(): Promise<Metadata> {
  return pageMetadata({
    title: "Airis Residence, Алматы - Официальный сайт",
    description: `${site.roomsCount} ${roomsWord(site.roomsCount)} в центре Алматы, ${site.address.street}. Завтрак включён, стойка регистрации 24/7. От ${formatPrice(await getPriceFrom())} за ночь — напрямую, без комиссии агрегаторов.`,
    path: "/",
  });
}

export default async function HomePage() {
  const rooms = await getRooms();
  const priceFrom = Math.min(...rooms.map((room) => room.price));

  return (
    <>
      <JsonLd data={faqJsonLd(faqItems.map((i) => ({ q: i.q, a: i.a })))} />
      {/* Порядок блоков — порядок вопросов гостя: какие номера и почём →
          почему здесь → как выглядит на самом деле → что входит → где это
          и как добраться → что рядом → условия → бронь.

          Раньше под первым экраном стояли события рядом, потом рассказ об
          отеле, и на телефоне номера начинались только с 4-го экрана
          (замер 2026-09-30). Кто пришёл за ценой, до неё не долистывал и
          уходил сравнивать на агрегатор. События полезны части гостей —
          они теперь рядом с картой, где и отвечают на вопрос «что рядом». */}
      <Hero priceFrom={priceFrom} />
      <Rooms rooms={rooms} />
      <About />
      <Gallery />
      <VideoShowcase />
      <Tour3D />
      <Amenities />
      <Location withEvents />
      <EventsNearby />
      <Faq />
      <CtaBook />
      {/* Компаниям — другой посетитель со своей кнопкой в меню. Частного
          гостя он не должен отвлекать между вопросами и бронью. */}
      <Corporate />
    </>
  );
}
