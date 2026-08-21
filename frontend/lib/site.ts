/**
 * Единственный источник правды по контенту отеля.
 * Меняешь тут — меняется на всём сайте, в schema.org и в sitemap.
 *
 * NAP (Name / Address / Phone) обязан совпадать СИМВОЛ В СИМВОЛ
 * с карточками 2ГИС, Google Business и Яндекс.Бизнес — иначе
 * локальное SEO разваливается.
 */

export const site = {
  name: "Airis Residence",
  legalName: 'ТОО "INCOME HOUSE"',
  tagline: "Отель в центре Алматы",
  url: "https://airisresidence.kz",
  locale: "ru_RU",
  roomsCount: 34,

  contacts: {
    phonePrimary: "+7 (777) 531-00-09",
    phonePrimaryRaw: "+77775310009",
    phoneCity: "+7 (727) 277-20-20",
    phoneCityRaw: "+77272772020",
    email: "airisresidence.kz@gmail.com",
    whatsapp: "https://wa.me/77775310009",
    telegram: "https://t.me/+77775310009",
    hours: "Круглосуточно, стойка регистрации 24/7",
  },

  address: {
    street: "ул. Наурызбай батыра, 134/2",
    city: "Алматы",
    region: "Алматинская область",
    postalCode: "050000",
    country: "KZ",
    countryName: "Казахстан",
    full: "Казахстан, г. Алматы, Алмалинский р-н, ул. Наурызбай батыра, 134/2",
    // Координаты дома 134 по Наурызбай батыра. Уточнить по карточке 2ГИС при запуске.
    lat: 43.24705,
    lng: 76.93705,
    mapUrl: "https://2gis.kz/almaty/search/Наурызбай%20батыра%20134%2F2",
    googleMapsUrl: "https://www.google.com/maps/search/?api=1&query=43.24705,76.93705",
  },

  legal: {
    bin: "200640012670",
    iik: "KZ8596503F0013625797KZT",
    bik: "IRTYKZKA",
    bank: 'Филиал АО "ForteBank" в г. Астана',
    kbe: "17",
  },

  policy: {
    checkIn: "14:00",
    checkOut: "12:00",
    // Платная услуга. Формулировки на сайте берутся отсюда — цену
    // и условия менять в одном месте, иначе страницы разъедутся.
    earlyCheckInFee: 20000,
    earlyCheckIn:
      "Ранний заезд и поздний выезд — платная услуга, 20 000 ₸, при наличии свободных номеров",
    pets: false,
    smoking: false,
    children: "Дети до 6 лет размещаются бесплатно на существующих спальных местах",
    payment: ["Наличные", "Visa", "Mastercard", "Безналичный расчёт для юрлиц"],
  },
} as const;

/* ------------------------------------------------------------------ */
/*  Номера                                                             */
/* ------------------------------------------------------------------ */

export type Room = {
  slug: string;
  name: string;
  shortName: string;
  price: number;
  area: string;
  capacity: number;
  beds: string;
  summary: string;
  description: string;
  features: string[];
  images: string[];
  /** Видеообзор номера. Загружается через админку, в запасном списке пуст. */
  video?: string;
  /** Кадр-заставка из ролика — показывается до нажатия play. */
  videoPoster?: string;
  /**
   * ID типа номера в Exely: по нему форма брони открывается сразу на нужном
   * номере (/booking?room-type=…). Живёт только здесь и в базу не идёт —
   * это идентификатор чужой системы, а не контент, который правят в админке.
   * Номера с боевого API приходят без него, поэтому поле необязательное,
   * а подставляется оно по slug в lib/rooms.ts.
   */
  beRoomType?: string;
};

/**
 * ⚠️ Фото разложены по типам номеров по визуальному признаку с сайта.
 * Comfort и Comfort Plus стоит перепроверить и переназначить.
 *
 * Папка с картинками у Comfort Plus осталась `luxe`: это внутренний
 * путь, гость его не видит, а переименование сломало бы ссылки на уже
 * загруженные фото. Код номера при этом comfort-plus.
 */
export const rooms: Room[] = [
  {
    slug: "standart-single",
    name: 'Номер "Standart Single"',
    shortName: "Standart Single",
    price: 25000,
    area: "16–18 м²",
    capacity: 1,
    beds: "Одна односпальная кровать",
    summary: "Компактный одноместный номер для деловой поездки на пару ночей.",
    description:
      "Одноместный номер с рабочим столом и полноценной ванной комнатой. Всё, что нужно для короткой командировки: тишина, быстрый интернет и завтрак с утра.",
    features: [
      "Односпальная кровать",
      "Рабочий стол и кресло",
      "Сейф",
      "Кондиционер",
      "Телевизор",
      "Wi-Fi",
      "Душ, фен, косметические принадлежности",
    ],
    images: [
      "/images/rooms/standart-single/01.jpg",
      "/images/rooms/standart-single/02.jpg",
      "/images/rooms/standart-single/03.jpg",
      "/images/rooms/standart-single/04.jpg",
    ],
    beRoomType: "5054709",
  },
  {
    slug: "standart",
    name: 'Номер "Standart"',
    shortName: "Standart",
    price: 45000,
    area: "18–20 м²",
    capacity: 2,
    beds: "Двуспальная кровать 180×200",
    summary: "Двуспальная кровать 180×200, мини-бар и сейф. Базовый выбор большинства гостей.",
    description:
      "Уютный и функциональный номер для краткосрочного проживания. Большая кровать, мягкий свет у изголовья, рабочая зона и розетки прямо у кровати.",
    features: [
      "Двуспальная кровать 180×200",
      "Сейф и мини-бар",
      "Телевизор, кондиционер, Wi-Fi",
      "Ванная комната с душем, фен",
      "Косметические принадлежности",
      "Рабочая зона, розетки у кровати",
    ],
    images: [
      "/images/rooms/standart/01.jpg",
      "/images/rooms/standart/02.jpg",
      "/images/rooms/standart/03.jpg",
      "/images/rooms/standart/04.jpg",
    ],
    beRoomType: "5050493",
  },
  {
    slug: "standart-twin",
    name: 'Номер "Standart Twin"',
    shortName: "Standart Twin",
    price: 45000,
    area: "23 м²",
    capacity: 2,
    beds: "Две раздельные кровати",
    summary: "Две раздельные кровати — для коллег в командировке или друзей.",
    description:
      "Номер с двумя раздельными кроватями и увеличенной площадью. Удобен, когда едут вдвоём по работе и нужны отдельные спальные места.",
    features: [
      "Две односпальные кровати",
      "Сейф и мини-бар",
      "Телевизор, кондиционер, Wi-Fi",
      "Ванная комната с душем, фен",
      "Рабочая зона",
      "Зона отдыха с креслом",
    ],
    images: ["/images/rooms/standart-twin/01.jpg", "/images/rooms/standart-twin/02.jpg"],
    beRoomType: "5050494",
  },
  {
    slug: "comfort",
    name: 'Номер "Comfort"',
    shortName: "Comfort",
    price: 50000,
    area: "25 м²",
    capacity: 2,
    beds: "Двуспальная кровать 180×200",
    summary: "Больше площади, отдельная зона отдыха и расширенное оснащение.",
    description:
      "Просторный номер для тех, кто остаётся дольше, чем на ночь. Отдельная зона отдыха, увеличенная рабочая зона и полноценная гардеробная секция.",
    features: [
      "Двуспальная кровать 180×200",
      "Зона отдыха с креслом",
      "Сейф и мини-бар",
      "Телевизор, кондиционер, Wi-Fi",
      "Ванная комната с душем, фен",
      "Гардеробная секция",
    ],
    images: [
      "/images/rooms/comfort/01.jpg",
      "/images/rooms/comfort/02.jpg",
      "/images/rooms/comfort/03.jpg",
    ],
    beRoomType: "5050496",
  },
  {
    slug: "comfort-plus",
    name: 'Номер "Comfort Plus"',
    shortName: "Comfort Plus",
    price: 70000,
    area: "30 м²",
    capacity: 2,
    beds: "Двуспальная кровать 180×200",
    summary: "Самый большой номер отеля: гостиная зона, премиальная отделка, вид на город.",
    description:
      "Люкс на 30 м² с выделенной гостиной зоной и премиальной отделкой. Подходит для длительного проживания и для гостей, которым важно пространство.",
    features: [
      "Двуспальная кровать 180×200",
      "Выделенная гостиная зона",
      "Сейф и мини-бар",
      "Телевизор, кондиционер, Wi-Fi",
      "Просторная ванная комната",
      "Халаты и тапочки",
      "Рабочее место",
    ],
    images: ["/images/rooms/luxe/01.jpg", "/images/rooms/luxe/02.jpg", "/images/rooms/luxe/03.jpg"],
    beRoomType: "5050495",
  },
];

export const getRoom = (slug: string) => rooms.find((r) => r.slug === slug);

export const priceFrom = Math.min(...rooms.map((r) => r.price));

/* ------------------------------------------------------------------ */
/*  Удобства отеля                                                     */
/* ------------------------------------------------------------------ */

export const amenities = [
  { title: "Завтрак включён", note: "Шведский стол каждое утро", icon: "breakfast" },
  { title: "Стойка 24/7", note: "Сотрудник на месте днём и ночью", icon: "reception" },
  { title: "Wi-Fi на всей территории", note: "Бесплатно, без ограничений", icon: "wifi" },
  { title: "Кондиционер в каждом номере", note: "Индивидуальное управление", icon: "climate" },
  { title: "Сейф и мини-бар", note: "В каждом номере", icon: "safe" },
  { title: "Оплата картой", note: "Visa, Mastercard, безнал для юрлиц", icon: "card" },
  { title: "Ежедневная уборка", note: "Смена белья по графику", icon: "clean" },
  { title: "Трансфер и такси", note: "Организуем по запросу", icon: "transfer" },
] as const;

/* ------------------------------------------------------------------ */
/*  Что рядом — важно и для гостя, и для локального SEO                */
/* ------------------------------------------------------------------ */

export const nearby = [
  { name: "Метро «Байконур»", distance: "700 м" },
  { name: "Проспект Абая", distance: "800 м" },
  { name: "Казахский национальный театр оперы и балета", distance: "1,4 км" },
  { name: "Национальный музей искусств РК", distance: "1,2 км" },
  { name: "Театр имени Мухтара Ауэзова", distance: "900 м" },
  { name: "Аэропорт Алматы", distance: "17 км" },
] as const;

export const navLinks = [
  { href: "/#nomera", label: "Номера" },
  { href: "/#otel", label: "Об отеле" },
  { href: "/#tur", label: "3D-тур" },
  { href: "/#raspolozhenie", label: "Расположение" },
  { href: "/kak-oplatit", label: "Оплата" },
  { href: "/kontakty", label: "Контакты" },
] as const;

export const formatPrice = (value: number) =>
  new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(value) + " ₸";
