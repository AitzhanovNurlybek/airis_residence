import { redirect } from "next/navigation";

import { PriceCheck } from "@/components/admin/PriceCheck";
import { RoomsBoard } from "@/components/admin/RoomsBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminRoom } from "@/lib/adminTypes";
import { getRoomsWithSource } from "@/lib/rooms";

export default async function AdminRoomsPage() {
  // Проверка сессии и данные независимы, поэтому идут разом: два await
  // подряд — это два перелёта до базы в Сиднее вместо одного по времени.
  //
  // Третьим — то, что видит гость. Если база не ответила в момент сборки,
  // сайт молча подставляет цены, зашитые в код, и держит их до часа. Молчание
  // тут и есть проблема: цены на страницах неверные, а узнать об этом неоткуда.
  const [signedIn, res, shown] = await Promise.all([
    isAdminSignedIn(),
    adminFetch("/api/admin/rooms"),
    getRoomsWithSource().catch(() => ({ source: "backend" as const, rooms: [] })),
  ]);
  if (!signedIn) redirect("/admin/login");
  const rooms: AdminRoom[] = res.ok ? await res.json() : [];

  return (
    <>
      {shown.source !== "backend" && (
        <div
          role="alert"
          className="mb-6 rounded-2xl border border-wine-400/40 bg-wine-600/15 px-5 py-4"
        >
          <p className="font-display text-lg text-wine-100">
            Сайт показывает гостям запасные цены
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-wine-100/85">
            База не ответила, и страницы отдают цены, зашитые в код при разработке. Они
            устарели. Правки в этом разделе гость сейчас не увидит. Если это не проходит
            само за несколько минут — напишите разработчику.
          </p>
        </div>
      )}
      <PriceCheck />
      <RoomsBoard initialRooms={rooms} />
    </>
  );
}
