import type { Metadata } from "next";
import { rooms as fallbackRooms, site, type Room } from "./site";
import { rooms as roomsWord } from "@/lib/plural";
import { counterpart, langOf, type Lang } from "./routes";
import { amenitiesEn, roomEn, siteEn } from "./en";

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
  const lang = langOf(path);

  // Пара на другом языке — для поисковика (hreflang). Русская версия —
  // x-default: её показывают тем, чей язык не русский и не английский.
  // Страница без пары (оферта, политика) остаётся без языковых ссылок.
  const ruPath = counterpart(path, "ru");
  const enPath = counterpart(path, "en");
  const languages =
    ruPath && enPath
      ? {
          ru: new URL(ruPath, BASE_URL).toString(),
          en: new URL(enPath, BASE_URL).toString(),
          "x-default": new URL(ruPath, BASE_URL).toString(),
        }
      : undefined;

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
    alternates: languages ? { canonical: url, languages } : { canonical: url },
    robots: noindex ? { index: false, follow: false } : { index: true, follow: true },
    openGraph: {
      type: "website",
      locale: lang === "en" ? "en_US" : site.locale,
      ...(languages ? { alternateLocale: lang === "en" ? [site.locale] : ["en_US"] } : {}),
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
export function hotelJsonLd(rooms: Room[] = fallbackRooms, lang: Lang = "ru") {
  const en = lang === "en";
  const roomPath = (slug: string) => (en ? `/en/rooms/${slug}` : `/nomera/${slug}`);
  return {
    "@context": "https://schema.org",
    "@type": "Hotel",
    "@id": `${BASE_URL}/#hotel`,
    name: site.name,
    legalName: site.legalName,
    url: en ? abs("/en") : BASE_URL,
    image: [abs("/images/hotel/lobby.jpg"), abs("/images/rooms/standart/01.jpg")],
    // «34 номеров» — ошибка склонения, а описание из разметки читают и
    // поисковики, и ИИ-помощники, и оно же попадает в выдачу. Число здесь
    // всегда двузначное, поэтому правило простое: 2–4 в конце — «номера»,
    // кроме 12–14, где всегда «номеров».
    description: en
      ? `${site.name} is a hotel in Almaty city centre: ${site.roomsCount} rooms, breakfast included, 24/7 front desk. ${siteEn.address.street}.`
      : `Отель ${site.name} в центре Алматы: ${site.roomsCount} ${roomsWord(site.roomsCount)}, завтрак включён, круглосуточная стойка регистрации. ${site.address.street}.`,
    telephone: site.contacts.phonePrimaryRaw,
    email: site.contacts.email,
    priceRange: "₸₸",
    currenciesAccepted: "KZT",
    paymentAccepted: (en ? siteEn.policy.payment : site.policy.payment).join(", "),
    checkinTime: site.policy.checkIn,
    checkoutTime: site.policy.checkOut,
    petsAllowed: site.policy.pets,
    smokingAllowed: site.policy.smoking,
    numberOfRooms: site.roomsCount,
    address: {
      "@type": "PostalAddress",
      streetAddress: en ? siteEn.address.street : site.address.street,
      addressLocality: en ? siteEn.address.city : site.address.city,
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
    amenityFeature: en
      ? [
          ...amenitiesEn.slice(0, 5).map((item) => ({
            "@type": "LocationFeatureSpecification",
            name: item.title,
            value: true,
          })),
          { "@type": "LocationFeatureSpecification", name: "Free parking", value: true },
        ]
      : [
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
      url: abs(roomPath(room.slug)),
    })),
    sameAs: [site.contacts.whatsapp, site.address.mapUrl],
  };
}

export function roomJsonLd(room: Room, lang: Lang = "ru") {
  const en = lang === "en";
  const path = en ? `/en/rooms/${room.slug}` : `/nomera/${room.slug}`;
  const text = en ? roomEn(room) : room;
  return {
    "@context": "https://schema.org",
    "@type": "HotelRoom",
    "@id": `${BASE_URL}${path}#room`,
    name: room.shortName,
    description: text.description,
    image: room.images.map(abs),
    url: abs(path),
    occupancy: {
      "@type": "QuantitativeValue",
      maxValue: room.capacity,
      unitCode: "C62",
    },
    bed: { "@type": "BedDetails", typeOfBed: text.beds },
    amenityFeature: text.features.map((name) => ({
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
      url: abs(path),
      priceSpecification: {
        "@type": "UnitPriceSpecification",
        price: room.price,
        priceCurrency: "KZT",
        unitText: en ? "per night" : "за ночь",
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
