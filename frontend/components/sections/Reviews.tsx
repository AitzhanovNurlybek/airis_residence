import { Reveal } from "@/components/ui/Reveal";
import { reviews } from "@/lib/site";

/**
 * Отзывы гостей — сразу под номерами.
 *
 * Порядок вопросов гостя: какие номера и почём → а что говорят другие →
 * как выглядит. Без чужого мнения цена у незнакомого отеля читается как
 * обещание, а с ним — как проверенный факт.
 *
 * Только настоящее: оценка и выдержки — с Яндекс Карт, дословно, и рядом
 * ссылки, по которым любой проверит. Разметку рейтинга для поисковиков
 * (AggregateRating) не ставим намеренно: Google не принимает отзывы о
 * компании на её же сайте и может посчитать это накруткой.
 */
function Stars({ count }: { count: number }) {
  return (
    <span className="text-sand-400" aria-label={`${count} из 5`} role="img">
      {"★".repeat(count)}
      <span className="text-white/15">{"★".repeat(5 - count)}</span>
    </span>
  );
}

export function Reviews() {
  return (
    <section aria-labelledby="otzyvy-title" className="border-y border-white/8 bg-ink-900/40">
      <div className="container-page py-14 md:py-20">
        <Reveal>
          <p className="eyebrow">Отзывы гостей</p>
          <div className="mt-4 flex flex-wrap items-end justify-between gap-x-10 gap-y-4">
            <h2
              id="otzyvy-title"
              className="max-w-2xl font-display text-[clamp(1.6rem,3.2vw,2.3rem)] leading-[1.15] font-semibold text-cream"
            >
              Что пишут те, кто уже жил у нас
            </h2>
            <a
              href={reviews.rating.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-baseline gap-3"
            >
              <span className="font-display text-4xl leading-none font-semibold text-sand-300">
                {reviews.rating.value}
              </span>
              <span className="text-sm leading-snug text-muted transition-colors group-hover:text-cream">
                на {reviews.rating.source}
                <br />
                {reviews.rating.count}
              </span>
            </a>
          </div>
        </Reveal>

        <ul className="mt-10 grid gap-5 md:grid-cols-3">
          {reviews.items.map((item, index) => (
            <Reveal key={item.author} delay={0.05 * index}>
              <li className="flex h-full flex-col rounded-2xl border border-white/10 bg-ink-950/50 p-6">
                <Stars count={item.stars} />
                <blockquote className="mt-4 flex-1 text-[0.95rem] leading-relaxed text-cream/85">
                  «{item.text}»
                </blockquote>
                <p className="mt-5 border-t border-white/8 pt-4 text-sm text-muted">
                  <span className="notranslate text-cream/80">{item.author}</span>
                  {" · "}
                  {item.date}
                </p>
              </li>
            </Reveal>
          ))}
        </ul>

        <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
          {reviews.links.map((link) => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sand-300 underline decoration-sand-400/40 underline-offset-4 transition-colors hover:text-cream"
            >
              {link.name} →
            </a>
          ))}
          <span className="text-xs text-muted">
            Выдержки из отзывов на Яндекс Картах без правок, оценка — на{" "}
            {new Date(reviews.checked).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}
          </span>
        </div>
      </div>
    </section>
  );
}
