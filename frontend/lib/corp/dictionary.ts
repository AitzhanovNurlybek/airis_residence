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

  booking: {
    title: "Новое бронирование",
    dates: "Даты проживания",
    checkIn: "Заезд",
    checkOut: "Выезд",
    guests: "Гости",
    adults: "Взрослых",
    children: "Детей",
    pickRooms: "Выберите номера",
    add: "Выбрать",
    remove: "Убрать",
    count: "Номеров",
    tooSmall: "Не вмещает выбранное число гостей",
    guest: "Кто едет",
    guestName: "Имя гостя",
    guestPhone: "Телефон гостя",
    comment: "Комментарий для менеджера",
    commentHint: "Ранний заезд, счёт на другое юрлицо, что-то ещё",
    summary: "Итого",
    perNightShort: "за ночь",
    nothingPicked: "Номера не выбраны",
    submit: "Отправить заявку",
    submitting: "Отправляем…",
    capacityLeft: "Мест в выбранных номерах",
    needDates: "Укажите даты заезда и выезда",
    badOrder: "Дата выезда должна быть позже заезда",
    inPast: "Дата заезда уже прошла",
    notEnough: "Выбранные номера не вмещают всех гостей",
    failed: "Не удалось отправить заявку. Попробуйте ещё раз или напишите менеджеру.",
  },

  employees: {
    title: "Сотрудники",
    subtitle: "Кто из компании может бронировать и что видит",
    add: "Добавить сотрудника",
    email: "Рабочая почта",
    fullName: "Имя и фамилия",
    phone: "Телефон",
    role: "Роль",
    roleAdmin: "Ответственный",
    roleEmployee: "Сотрудник",
    roleAdminHint: "заводит коллег и видит все брони компании",
    roleEmployeeHint: "бронирует и видит только свои",
    password: "Пароль",
    passwordHint: "Минимум 8 символов. Сообщите его сотруднику лично.",
    noPassword: "пароль не задан — войти не может",
    lastLogin: "Последний вход",
    never: "ни разу",
    active: "Активен",
    disabled: "Отключён",
    disable: "Отключить",
    enable: "Включить",
    save: "Сохранить",
    newPassword: "Новый пароль",
    setPassword: "Задать пароль",
    emailTaken: "Такая почта уже заведена",
    failed: "Не получилось сохранить",
    selfDisable: "Нельзя отключить собственный доступ",
  },

  password: {
    title: "Смена пароля",
    current: "Текущий пароль",
    next: "Новый пароль",
    repeat: "Повторите новый пароль",
    submit: "Сменить пароль",
    done: "Пароль изменён",
    mismatch: "Пароли не совпадают",
    tooShort: "Новый пароль короче 8 символов",
    wrongCurrent: "Текущий пароль не подходит",
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

  booking: {
    title: "Жаңа брондау",
    dates: "Тұру күндері",
    checkIn: "Кіру",
    checkOut: "Шығу",
    guests: "Қонақтар",
    adults: "Ересектер",
    children: "Балалар",
    pickRooms: "Нөмірлерді таңдаңыз",
    add: "Таңдау",
    remove: "Алып тастау",
    count: "Нөмір саны",
    tooSmall: "Таңдалған қонақ санына сыймайды",
    guest: "Кім барады",
    guestName: "Қонақтың аты",
    guestPhone: "Қонақтың телефоны",
    comment: "Менеджерге түсініктеме",
    commentHint: "Ерте кіру, шотты басқа заңды тұлғаға және тағы басқа",
    summary: "Жиыны",
    perNightShort: "тәулігіне",
    nothingPicked: "Нөмірлер таңдалмаған",
    submit: "Өтінім жіберу",
    submitting: "Жіберілуде…",
    capacityLeft: "Таңдалған нөмірлердегі орын",
    needDates: "Кіру және шығу күндерін көрсетіңіз",
    badOrder: "Шығу күні кіру күнінен кейін болуы керек",
    inPast: "Кіру күні өтіп кеткен",
    notEnough: "Таңдалған нөмірлер барлық қонақты сыйдырмайды",
    failed: "Өтінім жіберілмеді. Қайталап көріңіз немесе менеджерге жазыңыз.",
  },

  employees: {
    title: "Қызметкерлер",
    subtitle: "Компаниядан кім брондай алады және не көреді",
    add: "Қызметкер қосу",
    email: "Жұмыс поштасы",
    fullName: "Аты-жөні",
    phone: "Телефон",
    role: "Рөлі",
    roleAdmin: "Жауапты",
    roleEmployee: "Қызметкер",
    roleAdminHint: "әріптестерін қосады және компанияның барлық бронын көреді",
    roleEmployeeHint: "брондайды және тек өзінікін көреді",
    password: "Құпиясөз",
    passwordHint: "Кемінде 8 таңба. Қызметкерге жеке хабарлаңыз.",
    noPassword: "құпиясөз жоқ — кіре алмайды",
    lastLogin: "Соңғы кіру",
    never: "бірде-бір рет",
    active: "Белсенді",
    disabled: "Өшірілген",
    disable: "Өшіру",
    enable: "Қосу",
    save: "Сақтау",
    newPassword: "Жаңа құпиясөз",
    setPassword: "Құпиясөз қою",
    emailTaken: "Мұндай пошта тіркелген",
    failed: "Сақталмады",
    selfDisable: "Өз рұқсатыңызды өшіре алмайсыз",
  },

  password: {
    title: "Құпиясөзді ауыстыру",
    current: "Ағымдағы құпиясөз",
    next: "Жаңа құпиясөз",
    repeat: "Жаңа құпиясөзді қайталаңыз",
    submit: "Құпиясөзді ауыстыру",
    done: "Құпиясөз ауыстырылды",
    mismatch: "Құпиясөздер сәйкес келмейді",
    tooShort: "Жаңа құпиясөз 8 таңбадан қысқа",
    wrongCurrent: "Ағымдағы құпиясөз дұрыс емес",
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

  booking: {
    title: "New booking",
    dates: "Stay dates",
    checkIn: "Check-in",
    checkOut: "Check-out",
    guests: "Guests",
    adults: "Adults",
    children: "Children",
    pickRooms: "Choose rooms",
    add: "Select",
    remove: "Remove",
    count: "Rooms",
    tooSmall: "Does not fit the number of guests",
    guest: "Who is travelling",
    guestName: "Guest name",
    guestPhone: "Guest phone",
    comment: "Note for the manager",
    commentHint: "Early check-in, invoice to another entity, anything else",
    summary: "Total",
    perNightShort: "per night",
    nothingPicked: "No rooms selected",
    submit: "Send request",
    submitting: "Sending…",
    capacityLeft: "Capacity of selected rooms",
    needDates: "Choose check-in and check-out dates",
    badOrder: "Check-out must be after check-in",
    inPast: "The check-in date has already passed",
    notEnough: "Selected rooms do not fit all guests",
    failed: "Could not send the request. Try again or write to your manager.",
  },

  employees: {
    title: "Employees",
    subtitle: "Who can book and what they see",
    add: "Add employee",
    email: "Work email",
    fullName: "Full name",
    phone: "Phone",
    role: "Role",
    roleAdmin: "Account owner",
    roleEmployee: "Employee",
    roleAdminHint: "adds colleagues and sees every booking of the company",
    roleEmployeeHint: "books and sees only their own",
    password: "Password",
    passwordHint: "At least 8 characters. Give it to the employee in person.",
    noPassword: "no password yet — cannot sign in",
    lastLogin: "Last sign-in",
    never: "never",
    active: "Active",
    disabled: "Disabled",
    disable: "Disable",
    enable: "Enable",
    save: "Save",
    newPassword: "New password",
    setPassword: "Set password",
    emailTaken: "That email is already registered",
    failed: "Could not save",
    selfDisable: "You cannot disable your own access",
  },

  password: {
    title: "Change password",
    current: "Current password",
    next: "New password",
    repeat: "Repeat new password",
    submit: "Change password",
    done: "Password changed",
    mismatch: "Passwords do not match",
    tooShort: "The new password is shorter than 8 characters",
    wrongCurrent: "The current password is wrong",
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
