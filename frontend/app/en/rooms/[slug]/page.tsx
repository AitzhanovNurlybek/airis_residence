import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { site } from "@/lib/site";
import { formatPriceEn, guestsEn, roomEn } from "@/lib/en";
import { getRooms, getRoomBySlug } from "@/lib/rooms";
import { getRoomBookingHref } from "@/lib/booking";
import { breadcrumbJsonLd, pageMetadata, roomJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/JsonLd";
import { RoomGallery } from "@/components/ui/RoomGallery";
import { RoomVideo } from "@/components/ui/RoomVideo";
import { buttonClass } from "@/components/ui/Button";
import { DirectBadge } from "@/components/ui/DirectBadge";
import { IconArrow, IconPhone, IconWhatsApp } from "@/components/ui/Icons";
import { BeSearchForm } from "@/components/be-forms/BeSearchForm";
import { RoomName } from "@/components/ui/RoomName";

export async function generateStaticParams() {
  const rooms = await getRooms();
  return rooms.map((room) => ({ slug: room.slug }));
}

export async function generateMetadata(props: PageProps<"/en/rooms/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const found = await getRoomBySlug(slug);
  if (!found) return pageMetadata({ title: "Room not found", description: "", path: "/en/rooms", noindex: true });
  const room = roomEn(found);

  return pageMetadata({
    title: `${room.shortName} — ${room.area}, from ${formatPriceEn(room.price)}`,
    description: `${room.summary} Almaty city centre, breakfast included, check-in from ${site.policy.checkIn}.`,
    path: `/en/rooms/${room.slug}`,
    image: room.images[0],
  });
}

export default async function RoomPageEn(props: PageProps<"/en/rooms/[slug]">) {
  const { slug } = await props.params;
  const all = await getRooms();
  const found = all.find((r) => r.slug === slug);
  if (!found) notFound();
  const room = roomEn(found);
  const others = all
    .filter((r) => r.slug !== room.slug)
    .slice(0, 3)
    .map(roomEn);

  return (
    <>
      <JsonLd data={roomJsonLd(found, "en")} />
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", path: "/en" },
          { name: "Rooms", path: "/en/rooms" },
          { name: room.shortName, path: `/en/rooms/${room.slug}` },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+2.5rem)]">
        <div className="mb-10">
          <BeSearchForm />
        </div>

        <nav aria-label="Breadcrumbs" className="text-xs text-muted">
          <ol className="flex flex-wrap items-center gap-2">
            <li>
              <Link href="/en" className="transition-colors hover:text-sand-300">
                Home
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li>
              <Link href="/en/rooms" className="transition-colors hover:text-sand-300">
                Rooms
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li className="text-cream/80">
              <RoomName name={room.shortName} />
            </li>
          </ol>
        </nav>

        <div className="mt-10 grid gap-12 lg:grid-cols-[1.15fr_1fr] lg:gap-16">
          <div>
            <RoomGallery images={room.images} name={room.shortName} lang="en" />

            {room.video && (
              <RoomVideo src={room.video} poster={room.videoPoster || undefined} name={room.shortName} lang="en" />
            )}
          </div>

          <div>
            <p className="eyebrow">
              {room.area} · {guestsEn(room.capacity)}
            </p>
            <h1 className="mt-4 font-display text-[clamp(2.1rem,4.5vw,3.2rem)] leading-[1.06] font-semibold text-cream">
              <RoomName name={room.shortName} /> room
            </h1>
            <p className="mt-5 text-[1.02rem] leading-relaxed text-muted">{room.description}</p>

            <div className="mt-8 flex flex-col gap-4 rounded-2xl border border-white/10 bg-ink-900 p-6">
              <div>
                <span className="block text-[0.7rem] tracking-[0.14em] text-muted uppercase">per night from</span>
                <span className="mt-1.5 block font-display text-4xl text-sand-200">{formatPriceEn(room.price)}</span>
                <span className="mt-1.5 block text-xs text-muted">Breakfast included</span>
              </div>
              <DirectBadge lang="en" className="self-start" />
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <a href={getRoomBookingHref(room.beRoomType, "en")} className={buttonClass("primary", "lg")}>
                Book this room
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
                Call
              </a>
            </div>

            <h2 className="eyebrow mt-12">In the room</h2>
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
                ["Size", room.area],
                ["Beds", room.beds],
                ["Check-in", `from ${site.policy.checkIn}`],
                ["Check-out", `until ${site.policy.checkOut}`],
              ].map(([label, value]) => (
                <div key={label} className="bg-ink-900 p-5">
                  <dt className="text-xs tracking-[0.12em] text-muted uppercase">{label}</dt>
                  <dd className="mt-2 text-cream">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        <section className="mt-24 mb-8">
          <h2 className="font-display text-2xl text-cream md:text-3xl">Other rooms</h2>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {others.map((other) => (
              <Link
                key={other.slug}
                href={`/en/rooms/${other.slug}`}
                className="group flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-ink-900 p-6 transition-colors hover:border-sand-400/40"
              >
                <span>
                  <span className="block font-display text-xl text-cream">
                    <RoomName name={other.shortName} />
                  </span>
                  <span className="mt-1.5 block text-sm text-muted">
                    {other.area} · {formatPriceEn(other.price)}
                  </span>
                </span>
                <IconArrow className="size-5 shrink-0 text-sand-400 transition-transform can-hover:group-hover:translate-x-1" />
              </Link>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
