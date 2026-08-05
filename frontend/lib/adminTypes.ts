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
