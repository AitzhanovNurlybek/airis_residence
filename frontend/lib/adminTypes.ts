export type AdminRoom = {
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
