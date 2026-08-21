import { redirect } from "next/navigation";

import { CompaniesBoard } from "@/components/admin/CompaniesBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminCompany } from "@/lib/adminTypes";

export default async function AdminCompaniesPage() {
  if (!(await isAdminSignedIn())) redirect("/admin/login");

  const res = await adminFetch("/api/admin/corp/companies");
  const companies: AdminCompany[] = res.ok ? await res.json() : [];

  return <CompaniesBoard initial={companies} />;
}
