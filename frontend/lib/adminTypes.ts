export type AdminRoom = {
  slug: string;
  name: string;
  shortName: string;
  price: number;
  /** Цена за двоих. Ноль — столько же, сколько за одного. */
  priceDouble: number;
  /** Доплата за дополнительное место. Ноль — места нет. */
  extraBedPrice: number;
  area: string;
  capacity: number;
  beds: string;
  summary: string;
  description: string;
  features: string[];
  images: string[];
  /** Ссылка на видеообзор. Пусто — ролика нет. */
  video: string;
  /** Кадр-заставка из этого же ролика. Пусто — плеер без картинки. */
  videoPoster: string;
  sortOrder: number;
  isPublished: boolean;
};

export type AdminLead = {
  id: number;
  created_at: string;
  name: string;
  phone: string;
  email: string | null;
  check_in: string | null;
  check_out: string | null;
  adults: number;
  room: string | null;
  comment: string | null;
  status: "new" | "contacted" | "confirmed" | "cancelled";
};

export const LEAD_STATUSES: { value: AdminLead["status"]; label: string; tone: string }[] = [
  { value: "new", label: "Новая", tone: "border-sand-400/50 text-sand-200" },
  { value: "contacted", label: "Связались", tone: "border-white/25 text-cream/80" },
  { value: "confirmed", label: "Подтверждена", tone: "border-emerald-400/50 text-emerald-200" },
  { value: "cancelled", label: "Отменена", tone: "border-wine-400/50 text-wine-200" },
];

/* ------------------------------------------------------------------ */
/*  Корпоративные клиенты                                              */
/* ------------------------------------------------------------------ */

export type AdminCompany = {
  slug: string;
  name: string;
  bin: string;
  contractNumber: string;
  contractDate: string | null;
  paymentTerms: string;
  managerName: string;
  managerEmail: string;
  managerPhone: string;
  /** Скидка на весь прайс. Точечная цена в AdminCompanyRate важнее. */
  discountPercent: number;
  /**
   * Вычет за отказ от завтрака: на гостя за ночь. Завтрак входит в цену
   * любого номера, поэтому это вычет, а не доплата. Ноль — цена та же,
   * но выбор всё равно записывается: кухне нужно число гостей на утро.
   */
  breakfastPrice: number;
  isActive: boolean;
};

export type AdminCompanyUser = {
  id: number;
  email: string;
  fullName: string;
  phone: string;
  role: "admin" | "employee";
  isActive: boolean;
  lastLoginAt: string | null;
  /** Задан ли пароль. Пока не задан, войти нельзя. */
  hasPassword: boolean;
};

export type AdminCompanyRate = {
  roomSlug: string;
  price: number;
};

export type AdminCorpBookingItem = {
  roomSlug: string;
  roomName: string;
  roomsCount: number;
  pricePerNight: number;
  amount: number;
};

export type AdminCorpBooking = {
  id: number;
  number: string;
  hotelSlug: string;
  checkIn: string;
  checkOut: string;
  nights: number;
  adults: number;
  children: number;
  guestName: string;
  guestPhone: string;
  comment: string;
  mealPlan: "breakfast" | "none";
  status: "new" | "confirmed" | "invoiced" | "paid" | "cancelled";
  totalAmount: number;
  invoiceNumber: string;
  createdAt: string;
  cancelReason: string;
  createdByName: string;
  /** Чья заявка. В общем списке без этого непонятно, кому звонить. */
  companySlug: string;
  companyName: string;
  items: AdminCorpBookingItem[];
};

/**
 * Путь заявки от компании до оплаты.
 *
 * Порядок здесь — это порядок в жизни, и кнопки в админке идут так же:
 * менеджер подтверждает наличие, выставляет счёт, отмечает оплату.
 */
export const CORP_STATUSES: {
  value: AdminCorpBooking["status"];
  label: string;
  tone: string;
}[] = [
  { value: "new", label: "Новая заявка", tone: "border-sand-400/50 text-sand-200" },
  { value: "confirmed", label: "Подтверждена", tone: "border-white/25 text-cream/80" },
  { value: "invoiced", label: "Счёт выставлен", tone: "border-wine-400/50 text-wine-200" },
  { value: "paid", label: "Оплачена", tone: "border-emerald-400/50 text-emerald-200" },
  { value: "cancelled", label: "Отменена", tone: "border-white/15 text-muted" },
];

export type CorpStatus = AdminCorpBooking["status"];

/**
 * Что менеджеру делать с заявкой прямо сейчас.
 *
 * Раньше все пять статусов показывались одинаковыми серыми кнопками в ряд, и
 * выбрать следующий шаг можно было только зная процесс наизусть. Теперь
 * следующее действие — одно, названо глаголом и выделено; остальное убрано
 * с глаз.
 *
 * `next` — шаг вперёд по процессу. У оплаченной и отменённой его нет:
 * дальше идти некуда, и кнопка там была бы приглашением сломать данные.
 */
export const CORP_FLOW: Record<
  CorpStatus,
  {
    /** Подпись статуса и что это значит для менеджера. */
    label: string;
    meaning: string;
    /** Цвет левой полосы карточки — по нему список читается, не вчитываясь. */
    stripe: string;
    /** Плашка статуса. */
    pill: string;
    /** Следующий шаг: во что переводим и как называется кнопка. */
    next?: { to: CorpStatus; action: string };
  }
> = {
  new: {
    label: "Новая заявка",
    meaning: "Компания ждёт ответа. Проверьте, свободны ли номера.",
    stripe: "bg-sand-400",
    pill: "bg-sand-400/15 text-sand-200 border-sand-400/40",
    next: { to: "confirmed", action: "Подтвердить наличие" },
  },
  confirmed: {
    label: "Подтверждена",
    meaning: "Номера есть. Осталось выставить счёт.",
    stripe: "bg-sky-400",
    pill: "bg-sky-400/12 text-sky-200 border-sky-400/40",
    next: { to: "invoiced", action: "Выставить счёт" },
  },
  invoiced: {
    label: "Счёт выставлен",
    meaning: "Ждём оплату от компании.",
    stripe: "bg-wine-400",
    pill: "bg-wine-500/15 text-wine-200 border-wine-400/40",
    next: { to: "paid", action: "Отметить оплату" },
  },
  paid: {
    label: "Оплачена",
    meaning: "Готово. Занесите бронь в шахматку Exely.",
    stripe: "bg-emerald-400",
    pill: "bg-emerald-500/12 text-emerald-200 border-emerald-400/40",
  },
  cancelled: {
    label: "Отменена",
    meaning: "Заявка закрыта.",
    stripe: "bg-white/20",
    pill: "bg-white/5 text-muted border-white/15",
  },
};
