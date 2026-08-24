import type { Metadata } from "next";
import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { ConciergeChat } from "@/components/admin/ConciergeChat";
import { ExelyAvailability } from "@/components/admin/ExelyAvailability";
import { PaymentCheck } from "@/components/admin/PaymentCheck";
import { Shahmatka } from "@/components/admin/Shahmatka";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";

export const metadata: Metadata = {
  title: "Консьерж",
  robots: { index: false, follow: false },
};

/**
 * Страница про ИИ-консьержа: что он знает и что умеет.
 *
 * Раньше называлась «Шахматка», и это сбивало с толку. Настоящая шахматка
 * живёт в Exely, а здесь про другое — правильно ли ведёт себя консьерж.
 * Учебная шахматка тут лишь одна часть из четырёх, и она вообще не про работу
 * отеля.
 *
 * Части намеренно разного вида: настоящие данные в сплошной рамке, песочница —
 * в пунктирной и с пометкой. Смотреть их приходится рядом, и путать «свободно
 * на самом деле» с «свободно понарошку» нельзя.
 */

function Step({
  number,
  title,
  subtitle,
  sandbox = false,
  children,
}: {
  number: number;
  title: string;
  subtitle: string;
  sandbox?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="mt-12">
      <div className="flex items-start gap-4">
        <span
          className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm ${
            sandbox
              ? "border border-dashed border-sand-400/50 text-sand-300"
              : "bg-sand-400/15 text-sand-200"
          }`}
        >
          {number}
        </span>
        <div className="min-w-0">
          <h2 className="font-display text-2xl text-cream md:text-3xl">
            {title}
            {sandbox && (
              <span className="ml-3 align-middle text-xs tracking-wide text-sand-300 uppercase">
                понарошку
              </span>
            )}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">{subtitle}</p>
        </div>
      </div>
      <div className="mt-6 md:pl-12">{children}</div>
    </section>
  );
}

export default async function ConciergePage() {
  const [signedIn, board] = await Promise.all([
    isAdminSignedIn(),
    adminFetch("/api/admin/local/board")
      .then((res) => (res && res.ok ? res.json() : null))
      .catch(() => null),
  ]);
  if (!signedIn) redirect("/admin/login");

  return (
    <div>
      <h1 className="font-display text-3xl text-cream md:text-4xl">Консьерж</h1>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
        Здесь проверяют, правильно ли отвечает автоматический помощник, который будет
        переписываться с гостями в WhatsApp и Instagram. Заселением и настоящими бронями эта
        страница не управляет — для этого есть Exely.
      </p>

      <Step
        number={1}
        title="Что свободно на самом деле"
        subtitle="Настоящие остатки из Exely — те же, что видит гость в форме брони на сайте. Отсюда консьерж и узнаёт, есть ли места. Изменить их здесь нельзя, только посмотреть."
      >
        <ExelyAvailability />
      </Step>

      <Step
        number={2}
        title="Переписка с консьержем"
        subtitle="Напишите как гость и посмотрите, что он ответит. Это то же сообщение, которое уйдёт в WhatsApp. Под каждым ответом видно, смотрел ли он в систему бронирования или отвечал по справке об отеле."
      >
        <ConciergeChat />
      </Step>

      <Step
        number={3}
        title="Проверка присланного чека"
        subtitle="Гость присылает платёжку — система читает документ, сверяет получателя с реквизитами отеля, ищет следы правки и сводит с бронью. Чек — это заявление об оплате, а не сама оплата: деньги всё равно нужно увидеть в выписке."
      >
        <PaymentCheck />
      </Step>

      <Step
        number={4}
        sandbox
        title="Песочница"
        subtitle="Учебная копия шахматки в нашей базе. Нужна, чтобы проверить, как консьерж оформляет, переносит и отменяет брони: в настоящую Exely мы пока писать не можем, а проверить запись надо. Всё, что здесь стоит, — выдумка, на заселение это не влияет никак."
      >
        <div className="rounded-2xl border border-dashed border-sand-400/25 p-5">
          <Shahmatka initial={board} />
        </div>
      </Step>
    </div>
  );
}
