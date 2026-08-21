import type { Metadata } from "next";
import { rooms as fallbackRooms, site, type Room } from "./site";

export const BASE_URL = site.url;

/** Базовые метаданные страницы с каноникалом и OG. */
export function pageMetadata({
  title,
  description,
  path = "/",
  image = "/og.jpg",
  noindex = false,
}: {
  title: string;
  description: string;
  path?: string;
  image?: string;
  noindex?: boolean;
}): Metadata {
  const url = new URL(path, BASE_URL).toString();

  // Корневой лейаут дописывает к каждому заголовку «| Airis Residence».
  // Половина страниц называет отель и сама — в выдаче получалось
  // «Airis Residence, Алматы — официальный сайт | Airis Residence», а на
  // странице бронирования бренд стоял дважды при длине 88 символов.
  // Если имя отеля в заголовке уже есть, отдаём absolute и не даём шаблону
  // приписать его второй раз.
  const brandAlreadyThere = title.includes(site.name);

  return {
    title: brandAlreadyThere ? { absolute: title } : title,
    description,
    alternates: { canonical: url },
    robots: noindex ? { index: false, follow: false } : { index: true, follow: true },
    openGraph: {
      type: "website",
      locale: site.locale,
      url,
      siteName: site.name,
      title,
      description,
      images: [{ url: image, width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}

const abs = (p: string) => new URL(p, BASE_URL).toString();

/* ------------------------------------------------------------------ */
/*  JSON-LD                                                            */
/* ------------------------------------------------------------------ */

/**
 * Главная разметка. Тип Hotel наследует LocalBusiness — Google
 * использует её для карточки организации и для блока «Отели».
 */
export function hotelJsonLd(rooms: Room[] = fallbackRooms) {
  return {
    "@context": "https://schema.org",
    "@type": "Hotel",
    "@id": `${BASE_URL}/#hotel`,
    name: site.name,
    legalName: site.legalName,
    url: BASE_URL,
    image: [abs("/images/hotel/lobby.jpg"), abs("/images/rooms/standart/01.jpg")],
    description: `Отель ${site.name} в центре Алматы: ${site.roomsCount} номеров, завтрак включён, круглосуточная стойка регистрации. ${site.address.street}.`,
    telephone: site.contacts.phonePrimaryRaw,
    email: site.contacts.email,
    priceRange: "₸₸",
    currenciesAccepted: "KZT",
    paymentAccepted: site.policy.payment.join(", "),
    checkinTime: site.policy.checkIn,
    checkoutTime: site.policy.checkOut,
    petsAllowed: site.policy.pets,
    smokingAllowed: site.policy.smoking,
    numberOfRooms: site.roomsCount,
    address: {
      "@type": "PostalAddress",
      streetAddress: site.address.street,
      addressLocality: site.address.city,
      addressRegion: site.address.region,
      postalCode: site.address.postalCode,
      addressCountry: site.address.country,
    },
    geo: {
      "@type": "GeoCoordinates",
      latitude: site.address.lat,
      longitude: site.address.lng,
    },
    hasMap: site.address.googleMapsUrl,
    openingHoursSpecification: {
      "@type": "OpeningHoursSpecification",
      dayOfWeek: [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
      ],
      opens: "00:00",
      closes: "23:59",
    },
    amenityFeature: [
      { "@type": "LocationFeatureSpecification", name: "Бесплатный Wi-Fi", value: true },
      { "@type": "LocationFeatureSpecification", name: "Завтрак включён", value: true },
      { "@type": "LocationFeatureSpecification", name: "Кондиционер", value: true },
      { "@type": "LocationFeatureSpecification", name: "Круглосуточная стойка регистрации", value: true },
      { "@type": "LocationFeatureSpecification", name: "Сейф в номере", value: true },
      { "@type": "LocationFeatureSpecification", name: "Оплата картой", value: true },
    ],
    makesOffer: rooms.map((room) => ({
      "@type": "Offer",
      name: room.shortName,
      price: room.price,
      priceCurrency: "KZT",
      availability: "https://schema.org/InStock",
      url: abs(`/nomera/${room.slug}`),
    })),
    sameAs: [site.contacts.whatsapp, site.address.mapUrl],
  };
}

export function roomJsonLd(room: Room) {
  return {
    "@context": "https://schema.org",
    "@type": "HotelRoom",
    "@id": `${BASE_URL}/nomera/${room.slug}#room`,
    name: room.shortName,
    description: room.description,
    image: room.images.map(abs),
    url: abs(`/nomera/${room.slug}`),
    occupancy: {
      "@type": "QuantitativeValue",
      maxValue: room.capacity,
      unitCode: "C62",
    },
    bed: { "@type": "BedDetails", typeOfBed: room.beds },
    amenityFeature: room.features.map((name) => ({
      "@type": "LocationFeatureSpecification",
      name,
      value: true,
    })),
    containedInPlace: { "@id": `${BASE_URL}/#hotel` },
    offers: {
      "@type": "Offer",
      price: room.price,
      priceCurrency: "KZT",
      availability: "https://schema.org/InStock",
      url: abs(`/nomera/${room.slug}`),
      priceSpecification: {
        "@type": "UnitPriceSpecification",
        price: room.price,
        priceCurrency: "KZT",
        unitText: "за ночь",
      },
    },
  };
}

export function breadcrumbJsonLd(items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: abs(item.path),
    })),
  };
}

export function faqJsonLd(items: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
}
