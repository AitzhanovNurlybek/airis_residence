"use client";

import Image from "next/image";
import Link from "next/link";

import { rooms as fallbackRooms, formatPrice, type Room } from "@/lib/site";
import { getRoomBookingHref } from "@/lib/booking";
import { SectionHead } from "@/components/ui/SectionHead";
import { Reveal } from "@/components/ui/Reveal";
import { TiltCard } from "@/components/ui/TiltCard";
import { IconArrow } from "@/components/ui/Icons";
import { types as typesWord } from "@/lib/plural";

function RoomCard({ room, index }: { room: Room; index: number }) {
  // Первый номер — крупной карточкой: 5 карточек ложатся в сетку 3+3 без дыр.
  const wide = index === 0;

  return (
    <Reveal delay={(index % 3) * 0.08} className={wide ? "lg:col-span-2" : ""}>
      <TiltCard className="group h-full" intensity={5}>
        <article className="relative flex h-full flex-col overflow-hidden rounded-card border border-white/8 bg-ink-800 shadow-lift transition-shadow duration-500 can-hover:group-can-hover:hover:shadow-deep">
          {/* На телефоне все карточки во всю ширину — вертикальный кадр
              сделал бы ленту бесконечной, поэтому там 4:3 */}
          <div
            className={`relative overflow-hidden ${
              wide ? "aspect-16/10" : "aspect-4/3 md:aspect-4/5"
            }`}
          >
            <Image
              src={room.images[0]}
              alt={`${room.shortName} — ${room.area}, отель Airis Residence в Алматы`}
              fill
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 40vw"
              className="object-cover transition-transform duration-[900ms] ease-[cubic-bezier(0.16,1,0.3,1)] can-hover:group-hover:scale-[1.07]"
            />
            <div className="absolute inset-0 bg-linear-to-t from-ink-950 via-ink-950/25 to-transparent" />

            <span className="absolute top-4 left-4 rounded-full border border-white/15 bg-ink-950/65 px-3 py-1.5 text-[0.7rem] tracking-wide text-cream/90 backdrop-blur-md">
              {room.area} · до {room.capacity}{" "}
              {room.capacity === 1 ? "гостя" : "гостей"}
            </span>
          </div>

          <div className="flex flex-1 flex-col p-5 md:p-7">
            <h3 className="font-display text-xl text-cream md:text-[1.7rem]">{room.shortName}</h3>
            <p className="mt-2.5 flex-1 text-sm leading-relaxed text-muted md:mt-3">
              {room.summary}
            </p>

            <div className="mt-5 flex flex-wrap items-end justify-between gap-x-4 gap-y-4 border-t border-white/8 pt-5 md:mt-6">
              <div>
                <span className="block text-[0.7rem] tracking-[0.14em] text-muted uppercase">
                  за ночь
                </span>
                <span className="mt-1 block font-display text-2xl text-sand-200">
                  {formatPrice(room.price)}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Link
                  href={`/nomera/${room.slug}`}
                  className="rounded-full border border-white/12 px-4 py-2.5 text-sm text-cream/85 transition-colors hover:border-sand-300/50 hover:text-cream"
                >
                  Подробнее
                </Link>
                <a
                  href={getRoomBookingHref(room.beRoomType)}
                  aria-label={`Забронировать ${room.shortName}`}
                  className="grid size-10 place-items-center rounded-full bg-linear-to-b from-wine-500 to-wine-700 text-white transition-transform can-hover:hover:scale-105"
                >
                  <IconArrow className="size-4" />
                </a>
              </div>
            </div>
          </div>
        </article>
      </TiltCard>
    </Reveal>
  );
}

export function Rooms({ rooms = fallbackRooms }: { rooms?: Room[] }) {
  return (
    <section id="nomera" className="relative scroll-mt-24 py-20 md:py-32">
      <div className="container-page">
        <SectionHead
          eyebrow="Номера"
          title={
            <>
              {rooms.length} {typesWord(rooms.length)} номеров —
              <br className="hidden md:block" /> от компактного до люкса
            </>
          }
          description="Все номера с кондиционером, сейфом, мини-баром и собственной ванной комнатой. Завтрак включён в стоимость любого тарифа."
        />

        <div className="mt-10 grid gap-5 md:mt-14 md:grid-cols-2 md:gap-6 lg:grid-cols-3 lg:gap-7">
          {rooms.map((room, i) => (
            <RoomCard key={room.slug} room={room} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
