/**
 * Словарь корпоративного кабинета: русский, казахский, английский.
 *
 * Почему отдельно от `lib/i18n` для публичного сайта. Тот перевод меняет
 * маршрутизацию: префиксы `/kk` и `/en`, редиректы, hreflang, sitemap на три
 * языка — всё ради поисковиков. Кабинет закрыт паролем и не индексируется, ему
 * из этого не нужно ничего. Язык здесь — настройка человека, а не адрес
 * страницы, поэтому он живёт в куке, а переключатель просто её меняет.
 *
 * Полнота словарей проверяется типом: `Dictionary` выводится из русского,
 * и забыть строку в казахском или английском нельзя — сборка не пройдёт.
 */

export const LOCALES = ["ru", "kk", "en"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "ru";

/** Подписи в переключателе. Каждый язык назван на себе самом. */
export const LOCALE_LABELS: Record<Locale, string> = {
  ru: "RU",
  kk: "KZ",
  en: "EN",
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

const ru = {
  brand: "Airis Residence",
  portal: "Корпоративный раздел портала",

  nav: {
    cabinet: "Кабинет",
    bookings: "Мои бронирования",
    book: "Забронировать",
    employees: "Сотрудники",
    signOut: "Выход",
    back: "Назад",
  },

  login: {
    title: "Корпоративный раздел портала",
    subtitle: "Вход для корпоративных клиентов Airis Residence",
    email: "Корпоративная почта",
    password: "Пароль",
    submit: "Войти",
    forgot: "Забыли пароль?",
    // Пароль восстанавливает менеджер: почтовой рассылки у нас нет, и обещать
    // письмо со ссылкой, которого не будет, нельзя.
    forgotHint:
      "Доступ выдаёт менеджер Airis Residence. Напишите ему — он вышлет новый пароль.",
    failed: "Неверная почта или пароль",
    offline: "Сервер недоступен. Попробуйте ещё раз через минуту.",
  },

  cabinet: {
    title: "Кабинет компании",
    changePassword: "Сменить пароль",
    bin: "БИН",
    contract: "Договор",
    payment: "Оплата",
    manager: "Менеджер Airis Residence",
    phone: "Телефон",
    email: "Почта",
    activeBookings: "активных броней",
    totalAmount: "сумма, ₸",
    paidAmount: "оплачено, ₸",
    tiles: {
      book: "Забронировать",
      bookHint: "подбор номеров и корпоративные цены",
      bookings: "Мои бронирования",
      bookingsHint: "текущие и прошлые, статусы",
      finance: "Финансы",
      financeHint: "суммы и статусы бронирований",
      reports: "Отчёты",
      reportsHint: "расходы по сотрудникам",
      employees: "Сотрудники",
      employeesHint: "доступ в кабинет",
    },
  },

  bookings: {
    title: "Мои бронирования",
    create: "Новое бронирование",
    empty: "Бронирований пока нет.",
    emptyHint: "Оформите первое — цены уже корпоративные.",
    number: "№",
    dates: "Даты",
    category: "Категория",
    rooms: "Ном.",
    amount: "Сумма",
    status: "Статус",
    employee: "Сотрудник",
    cancel: "отменить",
    nights: { one: "ночь", few: "ночи", many: "ночей", other: "ночи" },
    invoice: "Счёт",
    cancelReason: "Причина",
  },

  status: {
    new: "Ожидает подтверждения",
    confirmed: "Подтверждено",
    invoiced: "Ожидает оплаты",
    paid: "Оплачено",
    cancelled: "Отменено",
  },

  // Честная подпись про то, как всё работает сейчас. Пока система
  // бронирования отеля не отдаёт наличие номеров, подтверждает менеджер —
  // и гость должен об этом знать до оформления, а не после.
  notice:
    "Онлайн-подтверждение подключается. Пока заявка уходит менеджеру отдела бронирования — он подтверждает номер и выставляет счёт.",

  common: {
    currency: "₸",
    perNight: "за ночь",
    corpRate: "корп. тариф",
    sitePrice: "на сайте",
    loading: "Загружаем…",
    error: "Что-то пошло не так",
    retry: "Повторить",
  },
} satisfies Record<string, unknown>;

/**
 * Словарь обязан быть сериализуемым: он уезжает пропсом в клиентские
 * компоненты, а функцию через границу сервер→клиент React не пропускает —
 * страница падает целиком. Поэтому склонения хранятся формами слова, а
 * собирает их обычный хелпер (formatNights), который каждая сторона
 * импортирует сама.
 */
export type Dictionary = typeof ru;

const kk: Dictionary = {
  brand: "Airis Residence",
  portal: "Порталдың корпоративтік бөлімі",

  nav: {
    cabinet: "Кабинет",
    bookings: "Менің брондарым",
    book: "Брондау",
    employees: "Қызметкерлер",
    signOut: "Шығу",
    back: "Артқа",
  },

  login: {
    title: "Порталдың корпоративтік бөлімі",
    subtitle: "Airis Residence корпоративтік клиенттеріне арналған кіру",
    email: "Корпоративтік пошта",
    password: "Құпиясөз",
    submit: "Кіру",
    forgot: "Құпиясөзді ұмыттыңыз ба?",
    forgotHint:
      "Кіру рұқсатын Airis Residence менеджері береді. Оған жазыңыз — жаңа құпиясөз жібереді.",
    failed: "Пошта немесе құпиясөз қате",
    offline: "Сервер қолжетімсіз. Бір минуттан кейін қайталап көріңіз.",
  },

  cabinet: {
    title: "Компания кабинеті",
    changePassword: "Құпиясөзді ауыстыру",
    bin: "БСН",
    contract: "Шарт",
    payment: "Төлем",
    manager: "Airis Residence менеджері",
    phone: "Телефон",
    email: "Пошта",
    activeBookings: "белсенді брон",
    totalAmount: "сома, ₸",
    paidAmount: "төленді, ₸",
    tiles: {
      book: "Брондау",
      bookHint: "нөмірлерді таңдау және корпоративтік бағалар",
      bookings: "Менің брондарым",
      bookingsHint: "ағымдағы және өткен, мәртебелері",
      finance: "Қаржы",
      financeHint: "брондау сомалары мен мәртебелері",
      reports: "Есептер",
      reportsHint: "қызметкерлер бойынша шығындар",
      employees: "Қызметкерлер",
      employeesHint: "кабинетке кіру рұқсаты",
    },
  },

  bookings: {
    title: "Менің брондарым",
    create: "Жаңа брондау",
    empty: "Әзірге брондау жоқ.",
    emptyHint: "Алғашқысын рәсімдеңіз — бағалар қазірдің өзінде корпоративтік.",
    number: "№",
    dates: "Күндер",
    category: "Санат",
    rooms: "Нөм.",
    amount: "Сома",
    status: "Мәртебе",
    employee: "Қызметкер",
    cancel: "болдырмау",
    nights: { one: "түн", few: "түн", many: "түн", other: "түн" },
    invoice: "Шот",
    cancelReason: "Себебі",
  },

  status: {
    new: "Растауды күтуде",
    confirmed: "Расталды",
    invoiced: "Төлемді күтуде",
    paid: "Төленді",
    cancelled: "Болдырылмады",
  },

  notice:
    "Онлайн растау қосылу үстінде. Әзірге өтінім брондау бөлімінің менеджеріне жіберіледі — ол нөмірді растап, шот ұсынады.",

  common: {
    currency: "₸",
    perNight: "тәулігіне",
    corpRate: "корп. тариф",
    sitePrice: "сайтта",
    loading: "Жүктелуде…",
    error: "Бірдеңе дұрыс болмады",
    retry: "Қайталау",
  },
};

const en: Dictionary = {
  brand: "Airis Residence",
  portal: "Corporate portal",

  nav: {
    cabinet: "Dashboard",
    bookings: "My bookings",
    book: "Book now",
    employees: "Employees",
    signOut: "Sign out",
    back: "Back",
  },

  login: {
    title: "Corporate portal",
    subtitle: "Sign in for Airis Residence corporate clients",
    email: "Work email",
    password: "Password",
    submit: "Sign in",
    forgot: "Forgot your password?",
    forgotHint:
      "Access is granted by your Airis Residence manager. Write to them and they will send a new password.",
    failed: "Wrong email or password",
    offline: "The server is unavailable. Please try again in a minute.",
  },

  cabinet: {
    title: "Company account",
    changePassword: "Change password",
    bin: "BIN",
    contract: "Contract",
    payment: "Payment",
    manager: "Airis Residence manager",
    phone: "Phone",
    email: "Email",
    activeBookings: "active bookings",
    totalAmount: "amount, ₸",
    paidAmount: "paid, ₸",
    tiles: {
      book: "Book now",
      bookHint: "check rooms and corporate rates",
      bookings: "My bookings",
      bookingsHint: "current and past, statuses",
      finance: "Finance",
      financeHint: "amounts and booking statuses",
      reports: "Reports",
      reportsHint: "expenses by employee",
      employees: "Employees",
      employeesHint: "access to the account",
    },
  },

  bookings: {
    title: "My bookings",
    create: "New booking",
    empty: "No bookings yet.",
    emptyHint: "Make the first one — corporate rates already apply.",
    number: "No.",
    dates: "Dates",
    category: "Room type",
    rooms: "Qty",
    amount: "Amount",
    status: "Status",
    employee: "Employee",
    cancel: "cancel",
    nights: { one: "night", few: "nights", many: "nights", other: "nights" },
    invoice: "Invoice",
    cancelReason: "Reason",
  },

  status: {
    new: "Awaiting confirmation",
    confirmed: "Confirmed",
    invoiced: "Awaiting payment",
    paid: "Paid",
    cancelled: "Cancelled",
  },

  notice:
    "Instant confirmation is being connected. For now your request goes to the reservations manager — they confirm the room and issue an invoice.",

  common: {
    currency: "₸",
    perNight: "per night",
    corpRate: "corporate rate",
    sitePrice: "on the website",
    loading: "Loading…",
    error: "Something went wrong",
    retry: "Try again",
  },
};

const DICTIONARIES: Record<Locale, Dictionary> = { ru, kk, en };

export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale] ?? DICTIONARIES[DEFAULT_LOCALE];
}

/**
 * Формат денег. Пробел между разрядами — неразрывный, иначе сумма переносится
 * посередине и «308 500 ₸» превращается в «308» на одной строке и «500 ₸» на
 * следующей. Локаль на разбивку не влияет, поэтому она одна для всех языков.
 */
export function formatMoney(amount: number): string {
  return new Intl.NumberFormat("ru-RU").format(amount).replace(/ |\s/g, " ");
}

/**
 * «3 ночи», «3 түн», «3 nights».
 *
 * Правила склонения у языков разные: в русском три формы и они зависят от
 * последней цифры, в казахском после числительного слово не меняется вовсе,
 * в английском форм две. Считать это вручную — гарантированная ошибка на
 * «21 ночь» и «111 ночей», поэтому берём Intl.PluralRules.
 */
export function formatNights(count: number, dict: Dictionary, locale: Locale): string {
  const rule = new Intl.PluralRules(locale).select(count);
  const forms = dict.bookings.nights;
  const word = rule in forms ? forms[rule as keyof typeof forms] : forms.other;
  return `${count} ${word}`;
}

/** Дата в виде 04.09.2026 — одинаково читается на всех трёх языках. */
export function formatDate(value: string, locale: Locale): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale === "en" ? "en-GB" : "ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}
