import { redirect } from "next/navigation";

import { FunnelBoard, type Funnel } from "@/components/admin/FunnelBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";

export default async function AdminFunnelPage() {
  const [signedIn, res] = await Promise.all([
    isAdminSignedIn(),
    adminFetch("/api/admin/funnel?days=30"),
  ]);
  if (!signedIn) redirect("/admin/login");

  // Пустая воронка — нормальное состояние (бот только запущен), а не ошибка.
  // Поэтому при сбое показываем ноль разговоров, а не белый экран.
  const data: Funnel = res.ok
    ? await res.json()
    : {
        дней: 30,
        разговоров: 0,
        этапы: [],
        потеряли_после_цен: 0,
        потеряли_после_ссылки: 0,
        молчат: 0,
        ждут_ответа: 0,
        дожали: 0,
        спрашивали_фото: 0,
        искали_свою_бронь: 0,
        разговоры: [],
      };

  return <FunnelBoard data={data} />;
}
