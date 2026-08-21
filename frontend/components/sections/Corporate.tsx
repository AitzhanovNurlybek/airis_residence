import Link from "next/link";

import { buttonClass } from "@/components/ui/Button";
import { IconArrow } from "@/components/ui/Icons";

/**
 * Вход для компаний на публичной главной.
 *
 * Отдельный блок, а не строчка в подвале: командировочный трафик приходит по
 * другим запросам («отель для командировок», «размещение сотрудников по
 * договору»), и человек, который ищет корпоративное размещение, должен
 * понимать за три секунды, что это про него, — иначе он уйдёт на агрегатор,
 * где отель платит комиссию.
 *
 * Кнопка ведёт на вход в кабинет, но рядом обязательно объяснение, кому он
 * нужен: сама по себе кнопка «Корпоративный кабинет» на сайте отеля выглядит
 * как чужая служебная дверь.
 */

const points = [
  {
    title: "Цены по договору",
    text: "Тариф закреплён в договоре и виден сотрудникам в кабинете. Не нужно каждый раз уточнять стоимость у менеджера.",
  },
  {
    title: "Оплата по счёту",
    text: "Постоплата и закрывающие документы на юрлицо. Сотруднику не приходится платить своей картой и собирать чеки.",
  },
  {
    title: "Несколько сотрудников",
    text: "Ответственный заводит коллег сам, видит все брони компании и расходы по каждому.",
  },
];

export function Corporate() {
  return (
    <section id="korporativnym" className="container-page py-20 md:py-28">
      <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-ink-900/60">
        <div className="grid gap-10 p-8 md:p-12 lg:grid-cols-[1fr_0.9fr] lg:gap-16">
          <div>
            <p className="eyebrow">Компаниям</p>
            <h2 className="mt-4 font-display text-[clamp(1.8rem,3.6vw,2.6rem)] leading-[1.1] font-semibold text-cream">
              Размещаете сотрудников регулярно?
            </h2>
            <p className="mt-5 max-w-xl text-[1.02rem] leading-relaxed text-muted">
              У Airis Residence есть закрытый раздел для корпоративных клиентов: своя цена
              по договору, бронирование без звонков и оплата по счёту на юрлицо. Подходит
              компаниям, которые селят командированных, подрядчиков и гостей из других
              городов.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/korporativnym-klientam" className={buttonClass("primary", "lg")}>
                Как это работает
                <IconArrow className="size-4" />
              </Link>
              <Link href="/corp/login" className={buttonClass("outline", "lg")}>
                Войти в кабинет
              </Link>
            </div>
            <p className="mt-4 text-xs text-muted">
              Доступ выдаёт отдел бронирования после подписания договора.
            </p>
          </div>

          <ul className="grid gap-5 self-center">
            {points.map((point) => (
              <li key={point.title} className="border-l border-sand-400/30 pl-5">
                <h3 className="text-[0.95rem] text-cream">{point.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{point.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
