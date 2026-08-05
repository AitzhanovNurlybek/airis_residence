import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { formatPrice, site } from "@/lib/site";
import { getRooms, getRoomBySlug } from "@/lib/rooms";
import { getBookingHref, bookingLinkTarget, isBookingLive } from "@/lib/booking";
import { breadcrumbJsonLd, pageMetadata, roomJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/JsonLd";
import { RoomGallery } from "@/components/ui/RoomGallery";
import { BookingBar } from "@/components/ui/BookingBar";
import { buttonClass } from "@/components/ui/Button";
import { IconArrow, IconPhone, IconWhatsApp } from "@/components/ui/Icons";

export async function generateStaticParams() {
  const rooms = await getRooms();
  return rooms.map((room) => ({ slug: room.slug }));
}

export async function generateMetadata(props: PageProps<"/nomera/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const room = await getRoomBySlug(slug);
  if (!room) return pageMetadata({ title: "Номер не найден", description: "", noindex: true });

  return pageMetadata({
    title: `${room.shortName} — ${room.area}, от ${formatPrice(room.price)} за ночь`,
    description: `${room.summary} Отель Airis Residence, ${site.address.city}, ${site.address.street}. Завтрак включён, заселение круглосуточно.`,
    path: `/nomera/${room.slug}`,
    image: room.images[0],
  });
}

export default async function RoomPage(props: PageProps<"/nomera/[slug]">) {
  const { slug } = await props.params;
  const rooms = await getRooms();
  const room = rooms.find((r) => r.slug === slug);
  if (!room) notFound();

  const others = rooms.filter((r) => r.slug !== room.slug).slice(0, 3);

  return (
    <>
      <JsonLd data={roomJsonLd(room)} />
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "Номера", path: "/nomera" },
          { name: room.shortName, path: `/nomera/${room.slug}` },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+2.5rem)]">
        <nav aria-label="Хлебные крошки" className="text-xs text-muted">
          <ol className="flex flex-wrap items-center gap-2">
            <li>
              <Link href="/" className="transition-colors hover:text-sand-300">
                Главная
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li>
              <Link href="/nomera" className="transition-colors hover:text-sand-300">
                Номера
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li className="text-cream/80">{room.shortName}</li>
          </ol>
        </nav>

        <div className="mt-10 grid gap-12 lg:grid-cols-[1.15fr_1fr] lg:gap-16">
          <div>
            <RoomGallery images={room.images} name={room.shortName} />
          </div>

          <div>
            <p className="eyebrow">{room.area} · до {room.capacity} гостей</p>
            <h1 className="mt-4 font-display text-[clamp(2.1rem,4.5vw,3.2rem)] leading-[1.06] font-semibold text-cream">
              {room.name}
            </h1>
            <p className="mt-5 text-[1.02rem] leading-relaxed text-muted">{room.description}</p>

            <div className="mt-8 flex items-end gap-6 rounded-2xl border border-white/10 bg-ink-900 p-6">
              <div>
                <span className="block text-[0.7rem] tracking-[0.14em] text-muted uppercase">
                  стоимость за ночь
                </span>
                <span className="mt-1.5 block font-display text-4xl text-sand-200">
                  {formatPrice(room.price)}
                </span>
                <span className="mt-1.5 block text-xs text-muted">Завтрак включён</span>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href={getBookingHref({ room: room.slug })}
                target={bookingLinkTarget}
                rel={bookingLinkTarget ? "noopener noreferrer" : undefined}
                className={buttonClass("primary", "lg")}
              >
                {isBookingLive ? "Забронировать" : "Оставить заявку"}
              </a>
              <a
                href={site.contacts.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonClass("outline", "lg")}
              >
                <IconWhatsApp className="size-4" />
                WhatsApp
              </a>
              <a href={`tel:${site.contacts.phonePrimaryRaw}`} className={buttonClass("ghost", "lg")}>
                <IconPhone className="size-4" />
                Позвонить
              </a>
            </div>

            <h2 className="eyebrow mt-12">Оснащение номера</h2>
            <ul className="mt-5 grid gap-x-8 gap-y-3 sm:grid-cols-2">
              {room.features.map((feature) => (
                <li key={feature} className="flex gap-3 text-sm text-cream/85">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-sand-400" />
                  {feature}
                </li>
              ))}
            </ul>

            <dl className="mt-10 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/8 text-sm">
              {[
                ["Площадь", room.area],
                ["Спальные места", room.beds],
                ["Заезд", site.policy.checkIn],
                ["Выезд", site.policy.checkOut],
              ].map(([label, value]) => (
                <div key={label} className="bg-ink-900 p-5">
                  <dt className="text-xs tracking-[0.12em] text-muted uppercase">{label}</dt>
                  <dd className="mt-2 text-cream">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        <div className="mt-16">
          <BookingBar roomSlug={room.slug} compact />
        </div>

        <section className="mt-24 mb-8">
          <h2 className="font-display text-2xl text-cream md:text-3xl">Другие номера</h2>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {others.map((other) => (
              <Link
                key={other.slug}
                href={`/nomera/${other.slug}`}
                className="group flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-ink-900 p-6 transition-colors hover:border-sand-400/40"
              >
                <span>
                  <span className="block font-display text-xl text-cream">{other.shortName}</span>
                  <span className="mt-1.5 block text-sm text-muted">
                    {other.area} · {formatPrice(other.price)}
                  </span>
                </span>
                <IconArrow className="size-5 shrink-0 text-sand-400 transition-transform group-hover:translate-x-1" />
              </Link>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
