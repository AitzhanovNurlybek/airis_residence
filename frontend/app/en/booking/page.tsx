import type { Metadata } from "next";

import { JsonLd } from "@/components/JsonLd";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { BeBookingForm } from "@/components/be-forms/BeBookingForm";
import { DirectBadge } from "@/components/ui/DirectBadge";
import { siteEn } from "@/lib/en";

export const metadata: Metadata = pageMetadata({
  title: "Book a room — Airis Residence, Almaty",
  description:
    "Book a room at Airis Residence directly: no booking-site markup, breakfast included, online card payment — cards from foreign banks accepted. Free cancellation up to 24 hours before arrival.",
  path: "/en/booking",
});

/**
 * Бронирование по-английски. Форма Exely та же, что на /booking; язык она
 * берёт из адреса страницы (lib/language.ts → bookingEngineLanguage), а
 * параметры — дату, ночи, гостей, номер, метки — читает из адреса сама.
 */
export default function BookingPageEn() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", path: "/en" },
          { name: "Booking", path: "/en/booking" },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+3rem)] pb-8">
        <p className="eyebrow">Booking</p>
        <h1 className="mt-4 font-display text-[clamp(2.1rem,4.6vw,3.4rem)] leading-[1.05] font-semibold text-cream">
          Book a room
        </h1>
        <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-3 text-sm text-muted">
          <DirectBadge lang="en" />
          <span>{siteEn.policy.cancellation.split(".")[0]}.</span>
        </div>

        <BeBookingForm />
      </div>
    </>
  );
}
