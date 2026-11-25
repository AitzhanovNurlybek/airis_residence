import type { Metadata } from "next";

import { Hotel3D } from "@/components/hotel3d/Hotel3D";
import { JsonLd } from "@/components/JsonLd";
import { CtaBook } from "@/components/sections/CtaBook";
import { hotel3dCats } from "@/lib/hotel3d";
import { getRooms } from "@/lib/rooms";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { site } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "Отель Airis Residence в 3D — этажи и номера",
  description:
    "Посмотрите отель в центре Алматы сверху и изнутри: снимите крышу, выберите этаж и зайдите в номер — днём или вечером, с ценой и бронированием без наценки.",
  path: "/otel-3d",
  image: "/3d/hero-night.webp",
});

export default async function Hotel3DPage() {
  const rooms = await getRooms();
  const cats = hotel3dCats(rooms);

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
            Три этажа в центре Алматы, {site.address.street}. «Войти в отель» —
            пройдёте к стойке, где вас встретит виртуальный администратор: ей
            можно задать любой вопрос об отеле. «Снять крышу» — увидите этажи;
            кружки — номера, нажмите на любой, и камера зайдёт внутрь. Вечер или
            день — переключатель в углу. Понравился номер — бронируйте здесь же,
            напрямую, без наценки площадок.
          </p>
        </header>

        <section className="container-page mt-10">
          <Hotel3D cats={cats} />
          <p className="mt-6 max-w-3xl text-xs leading-relaxed text-muted">
            Здание построено в 3D по поэтажным планам техпаспорта и показано
            так, как выглядит на самом деле. Интерьеры номеров — визуализация по
            реальным фото каждой категории. Расположение категорий на этажах —
            по планам отеля; конкретный номер комнаты назначает стойка при
            заселении. Отель работает круглосуточно.
          </p>
        </section>

        <CtaBook />
      </div>
    </>
  );
}
