import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ConciergeChat } from "@/components/admin/ConciergeChat";
import { Shahmatka } from "@/components/admin/Shahmatka";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";

export const metadata: Metadata = {
  title: "Шахматка",
  robots: { index: false, follow: false },
};

/**
 * Шахматка и переписка на одной странице.
 *
 * Вместе, а не по отдельности, потому что смысл именно в паре: ставите бронь
 * сверху, тут же спрашиваете консьержа снизу и видите, узнал он о ней или нет.
 * Через две вкладки это проверять неудобно.
 */
export default async function ShahmatkaPage() {
  const [signedIn, board] = await Promise.all([
    isAdminSignedIn(),
    adminFetch("/api/admin/local/board")
      .then((res) => (res && res.ok ? res.json() : null))
      .catch(() => null),
  ]);
  if (!signedIn) redirect("/admin/login");

  return (
    <div>
      <h1 className="font-display text-3xl text-cream md:text-4xl">Шахматка</h1>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
        Это учебная копия системы бронирования: та самая база, с которой разговаривает
        ИИ-консьерж. Настоящая шахматка живёт в Exely, доступа к ней пока нет. Поставьте бронь
        здесь — и консьерж внизу страницы сразу начнёт говорить, что номер занят.
      </p>

      <div className="mt-6 rounded-2xl border border-white/10 bg-ink-900/50 p-6">
        <h2 className="font-display text-xl text-cream">Как проверить за минуту</h2>
        <ol className="mt-4 grid gap-2.5 text-sm text-muted">
          <li>
            <span className="text-sand-300">1.</span> В календаре найдите день и категорию —
            там написано, сколько номеров свободно.
          </li>
          <li>
            <span className="text-sand-300">2.</span> Ниже в форме поставьте бронь на этот день.
            Клетка в календаре уменьшится на единицу.
          </li>
          <li>
            <span className="text-sand-300">3.</span> Спуститесь к переписке и спросите:
            «Есть свободные номера на такие-то даты?» Консьерж ответит по этой же базе.
          </li>
          <li>
            <span className="text-sand-300">4.</span> Займите категорию целиком — и он скажет,
            что свободных нет, и предложит другую.
          </li>
        </ol>
      </div>

      <div className="mt-8">
        <Shahmatka initial={board} />
      </div>

      <h2 className="mt-14 font-display text-3xl text-cream">Переписка с консьержем</h2>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
        То же самое, что придёт гостю в WhatsApp. Ответы настоящие, брони — тестовые.
      </p>
      <div className="mt-6">
        <ConciergeChat />
      </div>
    </div>
  );
}
