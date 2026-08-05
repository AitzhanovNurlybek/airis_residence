import type { Metadata } from "next";

import { BookingRequestForm } from "@/components/booking/BookingRequestForm";
import { BookingWidgetSlot } from "@/components/booking/BookingWidgetSlot";
import { JsonLd } from "@/components/JsonLd";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { bookingConfig } from "@/lib/booking";
import { site, formatPrice } from "@/lib/site";
import { getRooms } from "@/lib/rooms";
import { IconClock, IconPhone, IconWhatsApp } from "@/components/ui/Icons";

export const metadata: Metadata = pageMetadata({
  title: "Бронирование номера в отеле Airis Residence, Алматы",
  description:
    "Забронируйте номер в отеле Airis Residence напрямую: без комиссии агрегаторов, завтрак включён, подтверждение брони в течение 15 минут.",
  path: "/bronirovanie",
});

export default async function BookingPage(props: PageProps<"/bronirovanie">) {
  const search = await props.searchParams;
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

  const roomSlug = one(search.room) ?? "";
  const rooms = await getRooms();
  const room = rooms.find((r) => r.slug === roomSlug);
  const priceFrom = Math.min(...rooms.map((r) => r.price));

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "Бронирование", path: "/bronirovanie" },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+3rem)] pb-8">
        <div className="grid gap-12 lg:grid-cols-[1fr_0.8fr] lg:gap-16">
          <div>
            <p className="eyebrow">Бронирование</p>
            <h1 className="mt-4 font-display text-[clamp(2.1rem,4.6vw,3.4rem)] leading-[1.05] font-semibold text-cream">
              {room ? `Бронирование: ${room.shortName}` : "Забронировать номер"}
            </h1>
            <p className="mt-5 max-w-xl text-[1.02rem] leading-relaxed text-muted">
              {room
                ? `${room.area}, до ${room.capacity} гостей, ${formatPrice(room.price)} за ночь. Завтрак включён.`
                : `Оставьте заявку — подберём номер под ваши даты и подтвердим бронь. Номера от ${formatPrice(priceFrom)} за ночь, завтрак включён.`}
            </p>

            <div className="mt-10 space-y-6">
              <BookingWidgetSlot />

              {bookingConfig.mode !== "widget" && (
                <BookingRequestForm
                  rooms={rooms}
                  defaultRoom={roomSlug}
                  defaultCheckIn={one(search.checkin)}
                  defaultCheckOut={one(search.checkout)}
                  defaultAdults={Number(one(search.adults)) || 2}
                />
              )}
            </div>
          </div>

          <aside className="space-y-6 lg:pt-24">
            <div className="rounded-card border border-white/10 bg-ink-900 p-7">
              <h2 className="font-display text-xl text-cream">Быстрее — по телефону</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted">
                Стойка регистрации отвечает круглосуточно. Забронировать можно голосом
                за пару минут.
              </p>
              <div className="mt-6 space-y-3">
                <a
                  href={`tel:${site.contacts.phonePrimaryRaw}`}
                  className="flex items-center gap-3 rounded-xl border border-white/10 px-4 py-3.5 text-sm text-cream transition-colors hover:border-sand-400/40"
                >
                  <IconPhone className="size-4 text-sand-400" />
                  {site.contacts.phonePrimary}
                </a>
                <a
                  href={`tel:${site.contacts.phoneCityRaw}`}
                  className="flex items-center gap-3 rounded-xl border border-white/10 px-4 py-3.5 text-sm text-cream transition-colors hover:border-sand-400/40"
                >
                  <IconPhone className="size-4 text-sand-400" />
                  {site.contacts.phoneCity}
                </a>
                <a
                  href={site.contacts.whatsapp}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded-xl bg-[#25D366] px-4 py-3.5 text-sm font-medium text-white"
                >
                  <IconWhatsApp className="size-4" />
                  Написать в WhatsApp
                </a>
              </div>
            </div>

            <div className="rounded-card border border-white/10 bg-ink-900 p-7">
              <h2 className="eyebrow">Условия</h2>
              <dl className="mt-5 space-y-4 text-sm">
                <div className="flex items-start gap-3">
                  <IconClock className="mt-0.5 size-4 shrink-0 text-sand-400" />
                  <div>
                    <dt className="text-cream">Заезд с {site.policy.checkIn}, выезд до {site.policy.checkOut}</dt>
                    <dd className="mt-1 text-muted">{site.policy.earlyCheckIn}</dd>
                  </div>
                </div>
                <div className="hairline" />
                <div>
                  <dt className="text-cream">Оплата</dt>
                  <dd className="mt-1 text-muted">{site.policy.payment.join(", ")}</dd>
                </div>
                <div className="hairline" />
                <div>
                  <dt className="text-cream">Дети</dt>
                  <dd className="mt-1 text-muted">{site.policy.children}</dd>
                </div>
              </dl>
            </div>
          </aside>
        </div>
      </div>
    </>
  );
}
