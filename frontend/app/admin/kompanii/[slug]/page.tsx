import { notFound, redirect } from "next/navigation";

import { CompanyEditor } from "@/components/admin/CompanyEditor";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type {
  AdminCompany,
  AdminCompanyRate,
  AdminCompanyUser,
  AdminCorpBooking,
  AdminRoom,
} from "@/lib/adminTypes";

async function read<T>(path: string, fallback: T): Promise<T> {
  const res = await adminFetch(path).catch(() => null);
  if (!res || !res.ok) return fallback;
  return (await res.json()) as T;
}

export default async function AdminCompanyPage(props: PageProps<"/admin/kompanii/[slug]">) {
  if (!(await isAdminSignedIn())) redirect("/admin/login");

  const { slug } = await props.params;

  // Компанию читаем из общего списка: отдельного эндпоинта на одну нет, а
  // компаний у отеля десятки, не тысячи — лишний маршрут ради этого не нужен.
  const companies = await read<AdminCompany[]>("/api/admin/corp/companies", []);
  const company = companies.find((item) => item.slug === slug);
  if (!company) notFound();

  const [rooms, rates, users, bookings] = await Promise.all([
    read<AdminRoom[]>("/api/admin/rooms", []),
    read<AdminCompanyRate[]>(`/api/admin/corp/companies/${slug}/rates`, []),
    read<AdminCompanyUser[]>(`/api/admin/corp/companies/${slug}/users`, []),
    read<AdminCorpBooking[]>(`/api/admin/corp/bookings?company=${slug}`, []),
  ]);

  return (
    <CompanyEditor
      company={company}
      rooms={rooms}
      rates={rates}
      users={users}
      bookings={bookings}
    />
  );
}
