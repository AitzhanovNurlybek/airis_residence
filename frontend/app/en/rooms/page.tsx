import type { Metadata } from "next";

import { Rooms } from "@/components/sections/Rooms";
import { CtaBook } from "@/components/sections/CtaBook";
import { JsonLd } from "@/components/JsonLd";
import { BeSearchForm } from "@/components/be-forms/BeSearchForm";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { formatPriceEn, roomEn } from "@/lib/en";
import { getPriceFrom, getRooms } from "@/lib/rooms";

export async function generateMetadata(): Promise<Metadata> {
  const from = formatPriceEn(await getPriceFrom());
  return pageMetadata({
    title: `Rooms at Airis Residence, Almaty — from ${from}`,
    description: `Five room types from ${from} per night: Standart Single, Standart, Standart Twin, Comfort and Comfort Plus. 16 to 30 m², breakfast included, central Almaty.`,
    path: "/en/rooms",
  });
}

export default async function RoomsPageEn() {
  const rooms = (await getRooms()).map(roomEn);

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", path: "/en" },
          { name: "Rooms", path: "/en/rooms" },
        ])}
      />
      <div className="pt-[calc(var(--header-h)+3.5rem)]">
        <div className="mb-10">
          <BeSearchForm />
        </div>

        <header className="container-page max-w-3xl">
          <p className="eyebrow">Accommodation</p>
          <h1 className="mt-4 font-display text-[clamp(2.2rem,5vw,3.6rem)] leading-[1.05] font-semibold text-cream">
            Rooms at Airis Residence
          </h1>
          <p className="mt-5 text-[1.02rem] leading-relaxed text-muted">
            {rooms.length} room types. Every room has air conditioning, a safe, a minibar, a work area
            and a private bathroom. Breakfast is included in rates with breakfast.
          </p>
        </header>
        <Rooms rooms={rooms} lang="en" />
        <CtaBook lang="en" />
      </div>
    </>
  );
}
