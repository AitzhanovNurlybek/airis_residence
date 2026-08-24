import { NextResponse } from "next/server";

import { faqItems } from "@/lib/faq";
import { getRoomsWithSource } from "@/lib/rooms";
import { amenities, eventVenues, nearby, site } from "@/lib/site";

/**
 * Машиночитаемая выжимка всего, что отель рассказывает о себе.
 *
 * Зачем отдельная точка. ИИ-консьерж в WhatsApp и Instagram называет гостю
 * цену, время заезда и условия отмены. Это обещания от лица отеля, и если они
 * разойдутся с сайтом, гость приедет к неверной цифре. Разойтись они могут
 * ровно одним способом — если у консьержа будет своя копия фактов.
 *
 * Поэтому копии нет. Здесь импортируются те же самые модули, из которых
 * страницы сайта рисуют цены, услуги и вопросы-ответы, а номера приходят
 * из базы через тот же getRooms(), что и страница «Номера». Поменяли цену
 * в админке — консьерж узнает об этом тогда же, когда и сайт.
 *
 * Тайн здесь нет: всё это и так напечатано на публичных страницах, включая
 * реквизиты в подвале. Закрывать ключом нечего, но и в поиск отдавать незачем
 * — отсюда noindex.
 */

export const dynamic = "force-dynamic";

export async function GET() {
  const { rooms, source } = await getRoomsWithSource();

  // Запасной список цен зашит в код и отстаёт от админки. Гостю на странице
  // он спасает вёрстку, а консьержу нельзя отдавать его вовсе: тот назовёт
  // цену в переписке, и это будет обещание отеля. Лучше отказаться отвечать.
  if (source !== "backend") {
    return NextResponse.json(
      { error: "Номера недоступны: база не ответила, а запасные цены отдавать нельзя" },
      { status: 503, headers: { "X-Robots-Tag": "noindex, nofollow" } },
    );
  }

  const payload = {
    // Дата сборки, а не ручная версия: по ней видно, насколько свежие
    // факты держит у себя консьерж, если он их закешировал.
    generatedAt: new Date().toISOString(),

    hotel: {
      name: site.name,
      legalName: site.legalName,
      tagline: site.tagline,
      url: site.url,
      roomsCount: site.roomsCount,
      address: site.address.full,
      coordinates: { lat: site.address.lat, lng: site.address.lng },
      mapUrl: site.address.mapUrl,
      contacts: site.contacts,
      legal: site.legal,
    },

    policy: site.policy,

    rooms: rooms.map((room) => ({
      slug: room.slug,
      name: room.name,
      price: room.price,
      // Система бронирования отеля считает от числа гостей: в Comfort Plus
      // один гость стоит 50 000, а двое — 52 500. Ноль означает «столько же».
      priceDouble: room.priceDouble || room.price,
      extraBedPrice: room.extraBedPrice || 0,
      area: room.area,
      capacity: room.capacity,
      beds: room.beds,
      summary: room.summary,
      features: room.features,
      url: `${site.url}/nomera/${room.slug}`,
    })),

    priceFrom: rooms.length ? Math.min(...rooms.map((room) => room.price)) : null,

    amenities: amenities.map(({ title, note }) => ({ title, note })),
    nearby,
    eventVenues,
    faq: faqItems,

    // Куда консьерж передаёт разговор, когда упирается в свой предел:
    // цена вне прайса, групповая заявка, жалоба, изменение оплаченной брони.
    escalation: {
      phone: site.contacts.phonePrimary,
      email: site.contacts.email,
      hours: site.contacts.hours,
      corporate: `${site.url}/korporativnym-klientam`,
    },
  };

  return NextResponse.json(payload, {
    headers: { "X-Robots-Tag": "noindex, nofollow" },
  });
}
