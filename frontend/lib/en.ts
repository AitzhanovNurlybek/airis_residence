/**
 * Английские тексты сайта — для страниц под /en.
 *
 * Русский источник правды остаётся в lib/site.ts и lib/faq.ts: оттуда же
 * читает консьерж в WhatsApp (/api/knowledge), поэтому русские структуры
 * здесь не трогаются, а переводятся рядом. Правите факт в site.ts (цена
 * раннего заезда, время завтрака, расстояние) — поправьте и здесь: каждая
 * запись ниже повторяет русскую строку с тем же смыслом, без новых фактов.
 *
 * Названия номеров не переводятся ни на каком языке — это имена категорий
 * в Exely и на Booking.com (см. components/ui/RoomName.tsx).
 */

import { airport, eventVenues, nearby, reviews, site, type AirportOption, type Room } from "./site";

export const siteEn = {
  tagline: "Hotel in Almaty city centre",
  hours: "Open 24/7, front desk always staffed",
  address: {
    street: "134/2 Nauryzbai Batyr St.",
    district: "Almaly district",
    city: "Almaty",
    country: "Kazakhstan",
    full: "134/2 Nauryzbai Batyr St., Almaly district, Almaty 050000, Kazakhstan",
  },
  policy: {
    earlyCheckIn: "Early check-in and late check-out are a paid service, 20,000 ₸, subject to availability",
    payment: ["Cash", "Visa", "Mastercard", "Bank transfer for companies"],
    onlinePayment:
      "A booking on this website can be paid online by card right in the booking form. Cards issued by Kazakh and foreign banks are accepted",
    children: "Children under 6 stay free using existing beds",
    cancellation:
      "Free cancellation up to 24 hours before arrival. For later cancellations or no-shows, the first night is charged",
    refund:
      "Refunds are issued on the day of cancellation. The money reaches the card within 1–7 business days — the timing depends on the bank that issued the card, not on the hotel",
  },
} as const;

/* ------------------------------------------------------------------ */
/*  Номера                                                             */
/* ------------------------------------------------------------------ */

type RoomEn = Pick<Room, "summary" | "description" | "features" | "beds">;

/**
 * Тексты номеров по-английски — по slug. Цены, фото, площадь и вместимость
 * приходят из базы, как и на русских страницах; отсюда — только слова.
 * Номер, которого здесь нет (завели в админке позже), получит короткое
 * описание из площади и вместимости — см. roomEn().
 */
const roomTexts: Record<string, RoomEn> = {
  "standart-single": {
    beds: "One single bed",
    summary: "A compact single room for a business trip of a few nights.",
    description:
      "A single room with a work desk and a full private bathroom. Everything a short business trip needs: quiet, fast Wi-Fi and breakfast in the morning.",
    features: [
      "Single bed",
      "Work desk and chair",
      "In-room safe",
      "Air conditioning",
      "TV",
      "Wi-Fi",
      "Shower, hairdryer, toiletries",
    ],
  },
  standart: {
    beds: "Double bed 180×200",
    summary: "A 180×200 double bed, minibar and safe. The choice of most of our guests.",
    description:
      "A cosy, practical room for a short stay. A large bed, soft reading light at the headboard, a work area and sockets right next to the bed.",
    features: [
      "Double bed 180×200",
      "Safe and minibar",
      "TV, air conditioning, Wi-Fi",
      "Bathroom with shower, hairdryer",
      "Toiletries",
      "Work area, sockets by the bed",
    ],
  },
  "standart-twin": {
    beds: "Two separate beds",
    summary: "Two separate beds — for colleagues on a business trip or friends travelling together.",
    description:
      "A larger room with two separate beds. Comfortable when two people travel together for work and need their own beds.",
    features: [
      "Two single beds",
      "Safe and minibar",
      "TV, air conditioning, Wi-Fi",
      "Bathroom with shower, hairdryer",
      "Work area",
      "Seating area with an armchair",
    ],
  },
  comfort: {
    beds: "Double bed 180×200",
    summary: "More space, a separate seating area and extra amenities.",
    description:
      "A spacious room for guests who stay longer than a night. A separate seating area, a larger work area and a proper wardrobe section.",
    features: [
      "Double bed 180×200",
      "Seating area with an armchair",
      "Safe and minibar",
      "TV, air conditioning, Wi-Fi",
      "Bathroom with shower, hairdryer",
      "Wardrobe section",
    ],
  },
  "comfort-plus": {
    beds: "Double bed 180×200 and a sofa bed",
    summary: "Our largest room: a living area, premium finish and a view of the city.",
    description:
      "Comfort Plus is 30 m² with a dedicated living area and premium finish. Good for long stays and for guests who value space. A third guest sleeps on the sofa bed and is already included in the price.",
    features: [
      "Double bed 180×200",
      "Sofa bed for a third guest",
      "Dedicated living area",
      "Safe and minibar",
      "TV, air conditioning, Wi-Fi",
      "Spacious bathroom",
      "Bathrobes and slippers",
      "Work desk",
    ],
  },
};

/** «16–18 м²» → «16–18 m²». */
export const areaEn = (area: string) => area.replace(/м²/g, "m²").replace(/м2/g, "m²");

/** Номер с английскими текстами. Цена, фото, видео и площадь — из базы. */
export function roomEn(room: Room): Room {
  const text = roomTexts[room.slug];
  const area = areaEn(room.area);
  const guests = `up to ${room.capacity} ${room.capacity === 1 ? "guest" : "guests"}`;
  return {
    ...room,
    name: `${room.shortName} room`,
    area,
    beds: text?.beds ?? "",
    summary: text?.summary ?? `${area}, ${guests}. Breakfast included.`,
    description:
      text?.description ?? `${room.shortName}: ${area}, ${guests}. Air conditioning, safe, minibar and a private bathroom. Breakfast included.`,
    features: text?.features ?? ["Air conditioning", "Safe and minibar", "TV, Wi-Fi", "Private bathroom"],
  };
}

/** «до 2 гостей» по-английски. */
export const guestsEn = (n: number) => `up to ${n} ${n === 1 ? "guest" : "guests"}`;

/* ------------------------------------------------------------------ */
/*  Удобства, что рядом, события                                       */
/* ------------------------------------------------------------------ */

export const amenitiesEn = [
  { title: "Breakfast included", note: "Buffet from 7:30 to 10:30", icon: "breakfast" },
  { title: "24/7 front desk", note: "Staff on site day and night", icon: "reception" },
  { title: "Wi-Fi everywhere", note: "Free and unlimited", icon: "wifi" },
  { title: "Air conditioning", note: "Individually controlled in every room", icon: "climate" },
  { title: "Safe and minibar", note: "In every room", icon: "safe" },
  { title: "Card payment", note: "Visa, Mastercard, bank transfer for companies", icon: "card" },
  { title: "Daily housekeeping", note: "Linen changed on schedule", icon: "clean" },
  { title: "Transfer and taxi", note: "Arranged on request", icon: "transfer" },
] as const;

const nearbyNames: Record<string, string> = {
  "Метро «Байконур»": "Baikonur metro station",
  "Проспект Абая": "Abay Avenue",
  "Театр оперы и балета имени Абая": "Abay Opera and Ballet Theatre",
  "Дворец спорта имени Балуана Шолака": "Baluan Sholak Sports Palace",
  "Центральный стадион": "Central Stadium",
  "Дворец Республики": "Palace of the Republic",
  "Театр имени Мухтара Ауэзова": "Mukhtar Auezov Drama Theatre",
  "Музей искусств имени Кастеева": "Kasteyev State Museum of Arts",
  "Аэропорт Алматы": "Almaty Airport",
};

/** «9 минут» → «9 min walk». */
const walkEn = (walk: string) => {
  const minutes = walk.match(/\d+/)?.[0];
  return minutes ? `${minutes} min walk` : "";
};

/** «1,4 км» → «1.4 km», «700 м» → «700 m». */
export const distanceEn = (distance: string) =>
  distance.replace(",", ".").replace(/\s?км/, " km").replace(/\s?м$/, " m");

export const nearbyEn = nearby.map((place) => ({
  name: nearbyNames[place.name] ?? place.name,
  ruName: place.name,
  distance: distanceEn(place.distance),
  walk: walkEn(place.walk),
}));

const venueTexts: Record<string, { name: string; note: string; highlights: string[] }> = {
  "Центральный стадион": {
    name: "Central Stadium",
    note: "The city's main venue: world-class concerts and Kairat's European club matches.",
    highlights: [
      "Ye (Kanye West) performed here — August 2026",
      "Kairat played Real Madrid here, Champions League — September 2025",
    ],
  },
  "Дворец спорта имени Балуана Шолака": {
    name: "Baluan Sholak Sports Palace",
    note: "A concert and sports arena in the centre, open since 1967.",
    highlights: ["Tours, tournaments and shows all year round"],
  },
  "Театр оперы и балета имени Абая": {
    name: "Abay Opera and Ballet Theatre",
    note: "The closest big stage to the hotel — an easy walk after dinner.",
    highlights: ["Opera and ballet, the programme changes every week"],
  },
};

export const eventVenuesEn = eventVenues.map((venue) => ({
  ruName: venue.name,
  walk: walkEn(venue.walk),
  ...(venueTexts[venue.name] ?? { name: venue.name, note: venue.note, highlights: [...venue.highlights] }),
}));

/* ------------------------------------------------------------------ */
/*  Из аэропорта                                                       */
/* ------------------------------------------------------------------ */

const airportTexts: Record<string, Pick<AirportOption, "title" | "time" | "price" | "note">> = {
  transfer: {
    title: "Hotel transfer",
    time: "about 30 minutes",
    price: "from 5,000 ₸, depends on traffic",
    note: "Arranged on request. Send us your flight number and arrival time in advance.",
  },
  taxi: {
    title: "Taxi",
    time: "about 30 minutes, longer in traffic",
    price: "about 3,700 ₸",
    note: `Easiest to order in a taxi app. Address: ${siteEn.address.street} (in Russian: ${site.address.street}).`,
  },
  "bus-96": {
    title: "Bus 96 + trolleybus 7 or 30",
    time: "about 1.5 hours",
    price: "240 ₸ — two rides",
    note: "Bus 96 runs roughly every 12 minutes, the last one around 23:00.",
  },
  "bus-120": {
    title: "Bus 120 — no changes",
    time: "about 1.5 hours",
    price: "120 ₸",
    note: "Runs roughly every 9 minutes. The stop is a 23-minute walk from the terminal — hard with luggage.",
  },
  "bus-3-night": {
    title: "At night — bus 3",
    time: "about 2 hours",
    price: "120 ₸",
    note: "No changes, but it is infrequent — roughly once an hour.",
  },
};

const transferText = encodeURIComponent(
  "Hello! I need an airport transfer. Flight: , arrival time: , guests: ",
);

export const airportEn = {
  name: "Almaty International Airport",
  code: airport.code,
  distance: distanceEn(airport.distance),
  checked: airport.checked,
  options: airport.options.map((option) => ({ ...option, ...(airportTexts[option.id] ?? {}) })),
  payment:
    "A ride costs 120 ₸ with an Onay card or the QR code in the Onay app. The card is sold at terminals in the airport. Paying in cash costs more.",
  routeGoogle: airport.routeGoogle,
  route2gis: airport.route2gis,
  transferWhatsapp: `https://wa.me/${site.contacts.phonePrimaryRaw.replace(/\D/g, "")}?text=${transferText}`,
};

/* ------------------------------------------------------------------ */
/*  Отзывы                                                             */
/* ------------------------------------------------------------------ */

/**
 * Отзывы — те же выдержки с Яндекс Карт, переведённые. На странице прямо
 * сказано, что это перевод с русского, и рядом ссылка на оригинал: перевод
 * без пометки выглядел бы как отзыв, написанный по-английски.
 */
export const reviewsEn = {
  checked: reviews.checked,
  rating: {
    value: reviews.rating.value.replace(",", "."),
    count: "25 ratings",
    source: "Yandex Maps",
    url: reviews.rating.url,
  },
  links: [
    { name: "Reviews on Yandex Maps", url: reviews.links[0].url },
    { name: "Reviews on 2GIS", url: reviews.links[1].url },
  ],
  write: [
    { name: "TripAdvisor", note: "read by travellers from abroad", url: reviews.write[2].url },
    { name: "Yandex Maps", note: "read in Kazakhstan and Russia", url: reviews.write[1].url },
    { name: "2GIS", note: "read in Almaty", url: reviews.write[0].url },
  ],
  items: [
    {
      // Имена — латиницей: кириллица на английской странице читается как
      // ошибка перевода. Подписи те же, что на Яндекс Картах.
      author: "Lyudmila N.",
      date: "August 2026",
      stars: 5,
      text: "A wonderful cosy hotel in a very good location: the centre, transport nearby, lots of greenery and quiet rooms. … Excellent breakfasts, varied and filling!",
    },
    {
      author: "Alpamys B.",
      date: "September 2026",
      stars: 5,
      text: "The room is clean, cosy and comfortable, with everything you need. The staff are polite, friendly and always ready to help.",
    },
    {
      author: reviews.items[2].author,
      date: "August 2026",
      stars: 5,
      text: "Good value for money. Perfect location, everything is close. Because the building sits a little back in a courtyard, you can't hear the street.",
    },
  ],
} as const;

/* ------------------------------------------------------------------ */
/*  Частые вопросы                                                     */
/* ------------------------------------------------------------------ */

export const faqItemsEn = [
  {
    q: "What are the check-in and check-out times?",
    a: "Check-in from 14:00, check-out until 12:00. The front desk is open 24/7, with staff on site at night too. Early check-in or late check-out is a paid service, 20,000 ₸, and only if the room is free. Please ask when you book.",
  },
  {
    q: "Is breakfast included?",
    a: "Yes, in rates with breakfast. It is a buffet from 7:30 to 10:30: hot dishes, pastries, cold cuts, fruit and drinks. A halal breakfast is available too. You can also choose a rate without breakfast when booking.",
  },
  {
    q: "Can I pay with a foreign card?",
    a: "Yes. A booking on this website can be paid online by card in the booking form — cards issued by foreign banks are accepted. At the front desk we accept cash, Visa and Mastercard.",
  },
  {
    q: "Do the staff speak English?",
    a: "Yes. The front desk team speaks Russian, English and Turkish. You can also write to us on WhatsApp in English at any time.",
  },
  {
    q: "How do I get from the airport?",
    a: "The airport is 17 km away. A taxi takes about 30 minutes and costs about 3,700 ₸; the hotel can also arrange a transfer from 5,000 ₸. Buses run too — see the route options on this page.",
  },
  {
    q: "When will I get my money back if I cancel?",
    a: "Free cancellation is available up to 24 hours before arrival. The refund is issued on the day of cancellation and reaches your card within 1–7 business days, depending on your bank. If it has not arrived after seven business days, write to us with your booking number and the last four digits of the card.",
  },
  {
    q: "Is there parking?",
    a: "Yes, the hotel has free 24-hour parking with video surveillance.",
  },
  {
    q: "Can three people stay in one room?",
    a: "Yes, in the Comfort Plus room: the third guest sleeps on a sofa bed and is already included in the price. Other rooms are for one or two guests. An extra bed can be added on request for 15,000 ₸ per night with breakfast; a baby cot for children under 2 is free.",
  },
  {
    q: "Do you store luggage?",
    a: "Yes, we keep guests' luggage at the front desk before check-in and after check-out.",
  },
  {
    q: "Are pets allowed?",
    a: "Unfortunately, pets are not allowed.",
  },
] as const;

/* ------------------------------------------------------------------ */
/*  Навигация                                                          */
/* ------------------------------------------------------------------ */

export const navLinksEn = [
  { href: "/en#nomera", label: "Rooms" },
  { href: "/en#otzyvy", label: "Reviews" },
  { href: "/en#otel", label: "Hotel" },
  { href: "/en#raspolozhenie", label: "Location" },
  { href: "/en/almaty", label: "Almaty guide" },
  { href: "/en/payment", label: "Payment" },
  { href: "/en/contacts", label: "Contacts" },
] as const;

/** Подписи видеороликов из админки — по slug. Нет перевода — общий заголовок. */
export const videoTitlesEn: Record<string, { title: string; summary: string }> = {
  kuhnya: { title: "Kitchen and breakfast", summary: "Breakfast is included and served every morning." },
};

export const formatPriceEn = (value: number) =>
  new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value) + " ₸";
