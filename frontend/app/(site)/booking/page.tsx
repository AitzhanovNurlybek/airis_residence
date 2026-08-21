import type { Metadata } from "next";

import { JsonLd } from "@/components/JsonLd";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import {BeBookingForm} from "@/components/be-forms/BeBookingForm";

export const metadata: Metadata = pageMetadata({
  // Было «Бронирование номера в отеле Airis Residence, Алматы - Официальный
  // сайт» — 88 символов, и бренд в выдаче повторялся дважды.
  title: "Бронирование номера — Airis Residence, Алматы",
  description:
    "Забронируйте номер в отеле Airis Residence напрямую: без комиссии агрегаторов, завтрак включён, подтверждение брони в течение 15 минут.",
  path: "/booking",
});

export default async function BookingPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "Бронирование", path: "/booking" },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+3rem)] pb-8">
          <div>
            <p className="eyebrow">Бронирование</p>
            <h1 className="mt-4 font-display text-[clamp(2.1rem,4.6vw,3.4rem)] leading-[1.05] font-semibold text-cream">
              Забронировать номер
            </h1>

            <BeBookingForm />
          </div>
      </div>
    </>
  );
}
