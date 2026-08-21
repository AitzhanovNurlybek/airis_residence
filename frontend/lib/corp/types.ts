/**
 * Формы данных корпоративного кабинета — ровно то, что отдаёт бэкенд
 * (backend/app/schemas.py, раздел «Корпоративный кабинет»).
 *
 * Держим отдельным файлом, а не рядом с запросами: типы нужны и серверным
 * компонентам, и клиентским формам, а lib/corp/server.ts тянет за собой
 * `next/headers` и в браузерный бандл попасть не может.
 */

export type CorpRole = "admin" | "employee";

/** Состояние сделки. Порядок тот же, в каком бронь по ним идёт. */
export type BookingStatus = "new" | "confirmed" | "invoiced" | "paid" | "cancelled";

export type CorpUser = {
  id: number;
  email: string;
  fullName: string;
  phone: string;
  role: CorpRole;
  isActive: boolean;
  lastLoginAt: string | null;
  hasPassword: boolean;
};

export type CorpCompany = {
  slug: string;
  name: string;
  bin: string;
  contractNumber: string;
  contractDate: string | null;
  paymentTerms: string;
  managerName: string;
  managerEmail: string;
  managerPhone: string;
  discountPercent: number;
};

/** Первый экран кабинета одним запросом: карточка компании и счётчики. */
export type CorpMe = {
  user: CorpUser;
  company: CorpCompany;
  activeBookings: number;
  totalAmount: number;
  paidAmount: number;
};

export type CorpRoom = {
  slug: string;
  name: string;
  shortName: string;
  area: string;
  capacity: number;
  beds: string;
  summary: string;
  features: string[];
  images: string[];
  /** Цена с сайта — показывается рядом, чтобы выгода была видна. */
  publicPrice: number;
  corpPrice: number;
};

export type CorpBookingItem = {
  roomSlug: string;
  roomName: string;
  roomsCount: number;
  pricePerNight: number;
  amount: number;
};

export type CorpBooking = {
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
  status: BookingStatus;
  totalAmount: number;
  invoiceNumber: string;
  createdAt: string;
  cancelReason: string;
  createdByName: string;
  items: CorpBookingItem[];
};

/** Брони, которые ещё в работе. Повторяет ACTIVE_STATUSES на бэкенде. */
export const ACTIVE_STATUSES: BookingStatus[] = ["new", "confirmed", "invoiced"];

export function isActiveBooking(booking: CorpBooking): boolean {
  return ACTIVE_STATUSES.includes(booking.status);
}
