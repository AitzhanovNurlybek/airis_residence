import type { Metadata } from "next";

import { Hotel3D, type Cat, type CatInfo } from "@/components/hotel3d/Hotel3D";
import { JsonLd } from "@/components/JsonLd";
import { CtaBook } from "@/components/sections/CtaBook";
import { getRoomBookingHref } from "@/lib/booking";
import { getRooms } from "@/lib/rooms";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { formatPrice, site } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "Отель Airis Residence в 3D — этажи и номера",
  description:
    "Посмотрите отель в центре Алматы сверху и изнутри: снимите крышу, выберите этаж и номер — с фото, ценой и бронированием без наценки.",
  path: "/otel-3d",
  image: "/3d/hero-night.webp",
});

/** Категории модели → номера сайта (slug). Apart на сайте пока без страницы. */
const SLUG: Record<Exclude<Cat, "apart">, string> = {
  comfort_plus: "comfort-plus",
  comfort: "comfort",
  standart: "standart",
  twin: "standart-twin",
  single: "standart-single",
};

export default async function Hotel3DPage() {
  const rooms = await getRooms();
  const bySlug = new Map(rooms.map((r) => [r.slug, r]));

  const cats = {} as Record<Cat, CatInfo>;
  for (const [cat, slug] of Object.entries(SLUG) as [Exclude<Cat, "apart">, string][]) {
    const r = bySlug.get(slug);
    cats[cat] = {
      name: r?.shortName ?? slug,
      price: r?.price ?? null,
      priceText: r ? `от ${formatPrice(r.price)}` : "",
      area: r?.area ?? "",
      capacity: r?.capacity ?? 2,
      beds: r?.beds ?? "",
      summary: r?.summary ?? "",
      images: r?.images?.slice(0, 6) ?? [],
      href: `/nomera/${slug}`,
      bookHref: getRoomBookingHref(r?.beRoomType),
    };
  }
  // Apart продаётся в Exely (код 5070642), страницы на сайте пока нет —
  // в карточке видеообзор номера.
  cats.apart = {
    name: "Apart",
    price: null,
    priceText: "",
    area: "",
    capacity: 2,
    beds: "двуспальная кровать",
    summary:
      "Номер с мини-кухней: варочная панель, раковина, микроволновка, холодильник. Шкаф для вещей, душ. До двух гостей.",
    images: [],
    video: "/3d/apart.mp4",
    bookHref: getRoomBookingHref("5070642"),
  };

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "Отель в 3D", path: "/otel-3d" },
        ])}
      />
      <div className="pt-[calc(var(--header-h)+3rem)]">
        <header className="container-page max-w-3xl">
          <p className="eyebrow">Отель в 3D</p>
          <h1 className="mt-4 font-display text-[clamp(2.1rem,4.6vw,3.4rem)] leading-[1.05] font-semibold text-cream">
            Загляните в Airis Residence
          </h1>
          <p className="mt-5 text-[1.02rem] leading-relaxed text-muted">
            Три этажа в центре Алматы, {site.address.street}. Нажмите «Заглянуть внутрь» —
            крыша поднимется, и вы увидите этажи. Кружки — номера: нажмите на любой, чтобы
            посмотреть фото, цену и забронировать напрямую, без наценки площадок.
          </p>
        </header>

        <section className="container-page mt-10">
          <Hotel3D cats={cats} />
          <p className="mt-6 max-w-3xl text-xs leading-relaxed text-muted">
            Здание построено в 3D по поэтажным планам техпаспорта и показано так, как выглядит
            на самом деле. Расположение категорий номеров на этажах — ориентировочное: конкретный
            номер комнаты назначает стойка при заселении. Отель работает круглосуточно.
          </p>
        </section>

        <CtaBook />
      </div>
    </>
  );
}
