import Image from "next/image";

import { site, formatPrice } from "@/lib/site";
import { getPriceFrom } from "@/lib/rooms";
import { getBookingHref, bookingLinkTarget, isBookingLive } from "@/lib/booking";
import { buttonClass } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";
import { IconPhone, IconWhatsApp } from "@/components/ui/Icons";
import { DirectBadge } from "@/components/ui/DirectBadge";
import { formatPriceEn } from "@/lib/en";
import type { Lang } from "@/lib/routes";

export async function CtaBook({ lang = "ru" }: { lang?: Lang }) {
  const priceFrom = await getPriceFrom();
  const en = lang === "en";

  return (
    <section className="relative overflow-hidden py-20 md:py-32">
      <div className="container-page">
        <Reveal>
          <div className="relative overflow-hidden rounded-card border border-white/10 shadow-deep">
            <Image
              src="/images/rooms/luxe/02.jpg"
              alt={en ? "Comfort Plus room at Airis Residence" : "Номер Comfort Plus в отеле Airis Residence"}
              fill
              sizes="100vw"
              className="object-cover"
            />
            {/* На узком экране фото уходит под сплошную заливку —
                иначе текст ложится прямо на светлые пятна кадра */}
            <div className="absolute inset-0 bg-linear-to-b from-ink-950/92 to-ink-950/80 md:bg-linear-to-r md:from-ink-950 md:via-ink-950/85 md:to-ink-950/45" />
            <span className="grain-layer" />

            <div className="relative px-6 py-12 md:px-16 md:py-24">
              <div className="max-w-xl">
                <p className="eyebrow">{en ? "Booking" : "Бронирование"}</p>
                {en ? (
                  <>
                    <h2 className="mt-4 font-display text-[clamp(1.9rem,4vw,3.1rem)] leading-[1.08] font-semibold text-cream">
                      Book direct —{" "}
                      <span className="text-sand-300">it costs less than on booking sites</span>
                    </h2>
                    <p className="mt-5 text-[0.98rem] leading-relaxed text-cream/75">
                      No middleman commission on the official website. Rooms from{" "}
                      {formatPriceEn(priceFrom)} per night, breakfast included. Pay online by card —
                      cards issued by foreign banks are accepted.
                    </p>
                  </>
                ) : (
                  <>
                    <h2 className="mt-4 font-display text-[clamp(1.9rem,4vw,3.1rem)] leading-[1.08] font-semibold text-cream">
                      Бронируйте напрямую —{" "}
                      <span className="text-sand-300">выгоднее, чем на агрегаторах</span>
                    </h2>
                    <p className="mt-5 text-[0.98rem] leading-relaxed text-cream/75">
                      На официальном сайте нет комиссии посредников. Номера от{" "}
                      {formatPrice(priceFrom)} за ночь, завтрак включён. Подтверждаем бронь в
                      течение 15 минут в рабочее время.
                    </p>
                  </>
                )}
                <DirectBadge lang={lang} className="mt-5" />

                <div className="mt-8 flex flex-wrap gap-3 md:mt-9">
                  <a
                    href={getBookingHref({}, lang)}
                    target={bookingLinkTarget}
                    rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
                    className={buttonClass("primary", "lg", "w-full sm:w-auto")}
                  >
                    {en ? "Book online" : isBookingLive ? "Забронировать онлайн" : "Оставить заявку"}
                  </a>
                  <a
                    href={site.contacts.whatsapp}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={buttonClass("outline", "lg", "w-full sm:w-auto")}
                  >
                    <IconWhatsApp className="size-4" />
                    {en ? "WhatsApp us" : "Написать в WhatsApp"}
                  </a>
                  <a
                    href={`tel:${site.contacts.phonePrimaryRaw}`}
                    className={buttonClass("ghost", "lg", "w-full sm:w-auto")}
                  >
                    <IconPhone className="size-4" />
                    {site.contacts.phonePrimary}
                  </a>
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
