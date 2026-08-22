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
  const { slug } = await props.params;

  // Всё одним заходом. Раньше список компаний читался первым, и только потом
  // шли остальные запросы — два круга до Сиднея вместо одного. Ни один из них
  // не зависит от другого: имя компании нужно для показа, а не для запросов.
  const [signedIn, companies, rooms, rates, users, bookings] = await Promise.all([
    isAdminSignedIn(),
    read<AdminCompany[]>("/api/admin/corp/companies", []),
    read<AdminRoom[]>("/api/admin/rooms", []),
    read<AdminCompanyRate[]>(`/api/admin/corp/companies/${slug}/rates`, []),
    read<AdminCompanyUser[]>(`/api/admin/corp/companies/${slug}/users`, []),
    read<AdminCorpBooking[]>(`/api/admin/corp/bookings?company=${slug}`, []),
  ]);
  if (!signedIn) redirect("/admin/login");

  const company = companies.find((item) => item.slug === slug);
  if (!company) notFound();

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
