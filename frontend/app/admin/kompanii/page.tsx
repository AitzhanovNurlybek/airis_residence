import { redirect } from "next/navigation";

import { CompaniesBoard } from "@/components/admin/CompaniesBoard";
import { CorpInbox } from "@/components/admin/CorpInbox";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminCompany, AdminCorpBooking } from "@/lib/adminTypes";

async function read<T>(path: string, fallback: T): Promise<T> {
  const res = await adminFetch(path).catch(() => null);
  if (!res || !res.ok) return fallback;
  return (await res.json()) as T;
}

export default async function AdminCompaniesPage() {
  // Заявки тянем вместе со списком: менеджер должен увидеть, что его ждёт,
  // не открывая компании по очереди. Проверка сессии идёт тем же заходом —
  // иначе это лишний перелёт до базы перед каждой страницей.
  const [signedIn, companies, bookings] = await Promise.all([
    isAdminSignedIn(),
    read<AdminCompany[]>("/api/admin/corp/companies", []),
    read<AdminCorpBooking[]>("/api/admin/corp/bookings", []),
  ]);
  if (!signedIn) redirect("/admin/login");

  return (
    <>
      <CorpInbox bookings={bookings} />
      <CompaniesBoard initial={companies} />
    </>
  );
}
