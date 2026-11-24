import type { Cat, CatInfo } from "@/components/hotel3d/Hotel3D";
import { getRoomBookingHref } from "@/lib/booking";
import type { getRooms } from "@/lib/rooms";
import { formatPrice } from "@/lib/site";

/** Категории 3D-модели → номера сайта (slug). Apart на сайте пока без страницы. */
const SLUG: Record<Exclude<Cat, "apart">, string> = {
  comfort_plus: "comfort-plus",
  comfort: "comfort",
  standart: "standart",
  twin: "standart-twin",
  single: "standart-single",
};

/**
 * Данные карточек номеров для «Отель в 3D» — из тех же номеров, что на сайте
 * (цены и фото из админки). Нужны и странице /otel-3d, и главной.
 */
export function hotel3dCats(
  rooms: Awaited<ReturnType<typeof getRooms>>,
): Record<Cat, CatInfo> {
  const bySlug = new Map(rooms.map((r) => [r.slug, r]));
  const cats = {} as Record<Cat, CatInfo>;
  for (const [cat, slug] of Object.entries(SLUG) as [
    Exclude<Cat, "apart">,
    string,
  ][]) {
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
  return cats;
}
