import { notFound, redirect } from "next/navigation";

import { RoomEditor } from "@/components/admin/RoomEditor";
import { NewRoomForm } from "@/components/admin/NewRoomForm";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminRoom } from "@/lib/adminTypes";

export default async function AdminRoomPage(props: PageProps<"/admin/nomera/[slug]">) {
  if (!(await isAdminSignedIn())) redirect("/admin/login");

  const { slug } = await props.params;

  // Специальный адрес для создания нового номера
  if (slug === "novyi") return <NewRoomForm />;

  const res = await adminFetch(`/api/admin/rooms/${slug}`);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error("Не удалось загрузить номер");

  const room: AdminRoom = await res.json();
  return <RoomEditor room={room} />;
}
