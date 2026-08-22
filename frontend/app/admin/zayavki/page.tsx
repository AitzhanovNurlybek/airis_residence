import { redirect } from "next/navigation";

import { LeadsBoard } from "@/components/admin/LeadsBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminLead, AdminRoom } from "@/lib/adminTypes";

export default async function AdminLeadsPage() {
  const [signedIn, leadsRes, roomsRes] = await Promise.all([
    isAdminSignedIn(),
    adminFetch("/api/admin/leads?limit=200"),
    adminFetch("/api/admin/rooms"),
  ]);
  if (!signedIn) redirect("/admin/login");

  const leads: AdminLead[] = leadsRes.ok ? await leadsRes.json() : [];
  const rooms: AdminRoom[] = roomsRes.ok ? await roomsRes.json() : [];

  return <LeadsBoard initialLeads={leads} rooms={rooms} />;
}
