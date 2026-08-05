import { redirect } from "next/navigation";

import { LeadsBoard } from "@/components/admin/LeadsBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminLead, AdminRoom } from "@/lib/adminTypes";

export default async function AdminLeadsPage() {
  if (!(await isAdminSignedIn())) redirect("/admin/login");

  const [leadsRes, roomsRes] = await Promise.all([
    adminFetch("/api/admin/leads?limit=200"),
    adminFetch("/api/admin/rooms"),
  ]);

  const leads: AdminLead[] = leadsRes.ok ? await leadsRes.json() : [];
  const rooms: AdminRoom[] = roomsRes.ok ? await roomsRes.json() : [];

  return <LeadsBoard initialLeads={leads} rooms={rooms} />;
}
