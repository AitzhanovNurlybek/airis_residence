import { redirect } from "next/navigation";

import { RoomsBoard } from "@/components/admin/RoomsBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminRoom } from "@/lib/adminTypes";

export default async function AdminRoomsPage() {
  // Проверка сессии и данные независимы, поэтому идут разом: два await
  // подряд — это два перелёта до базы в Сиднее вместо одного по времени.
  const [signedIn, res] = await Promise.all([
    isAdminSignedIn(),
    adminFetch("/api/admin/rooms"),
  ]);
  if (!signedIn) redirect("/admin/login");
  const rooms: AdminRoom[] = res.ok ? await res.json() : [];

  return <RoomsBoard initialRooms={rooms} />;
}
