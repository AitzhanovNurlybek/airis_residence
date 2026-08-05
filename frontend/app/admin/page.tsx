import { redirect } from "next/navigation";

import { RoomsBoard } from "@/components/admin/RoomsBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminRoom } from "@/lib/adminTypes";

export default async function AdminRoomsPage() {
  if (!(await isAdminSignedIn())) redirect("/admin/login");

  const res = await adminFetch("/api/admin/rooms");
  const rooms: AdminRoom[] = res.ok ? await res.json() : [];

  return <RoomsBoard initialRooms={rooms} />;
}
