import { ReviewForm } from "@/components/sections/ReviewForm";
import { Reveal } from "@/components/ui/Reveal";
import { BACKEND_URL, CONTENT_TAG } from "@/lib/rooms";
import { reviews } from "@/lib/site";

type SiteReview = { id: number; name: string; text: string; stars: number; stay: string; created_at: string };

/**
 * Отзывы, оставленные на сайте и опубликованные в админке. Кеш снимается
 * той же меткой, что у номеров: опубликовали — гость видит сразу.
 */
async function siteReviews(): Promise<SiteReview[]> {
  if (!BACKEND_URL) return [];
  try {
    const res = await fetch(`${BACKEND_URL}/api/reviews`, { next: { revalidate: 600, tags: [CONTENT_TAG] } });
    return res.ok ? ((await res.json()) as SiteReview[]) : [];
  } catch {
    return [];
  }
}

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

export async function Reviews() {
  const own = await siteReviews();
  return (
    <section
      id="otzyvy"
      aria-labelledby="otzyvy-title"
      className="scroll-mt-24 border-y border-white/8 bg-ink-900/40"
    >
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

        {own.length > 0 && (
          <div className="mt-12">
            <h3 className="font-display text-xl font-semibold text-cream">Отзывы с нашего сайта</h3>
            <ul className="mt-5 grid gap-5 md:grid-cols-3">
              {own.slice(0, 6).map((item) => (
                <li key={item.id} className="flex h-full flex-col rounded-2xl border border-white/10 bg-ink-950/50 p-6">
                  <Stars count={item.stars} />
                  <blockquote className="mt-4 flex-1 text-[0.95rem] leading-relaxed whitespace-pre-line text-cream/85">
                    «{item.text}»
                  </blockquote>
                  <p className="mt-5 border-t border-white/8 pt-4 text-sm text-muted">
                    <span className="notranslate text-cream/80">{item.name}</span>
                    {item.stay ? ` · ${item.stay}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Гость, который уже жил у нас, ищет, где оставить отзыв, — и
            чаще всего не находит. Форма — прямо здесь (отзыв хранится у нас
            и выходит после проверки), а рядом кнопки на карты: там отзыв
            увидят те, кто ещё выбирает отель. */}
        <Reveal>
          <div className="mt-12 rounded-2xl border border-sand-400/20 bg-ink-950/50 p-6 md:p-8">
            <h3 className="font-display text-xl font-semibold text-cream">Жили у нас? Оставьте отзыв</h3>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
              Пара строк о том, что понравилось и что стоит улучшить, помогает другим гостям выбрать, а
              нам — стать лучше.
            </p>
            <div className="mt-6">
              <ReviewForm />
            </div>
            <p className="mt-8 text-sm text-muted">Или на картах — там отзыв прочитают те, кто ещё выбирает:</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              {reviews.write.map((place) => (
                <a
                  key={place.url}
                  href={place.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex flex-col rounded-xl border border-white/10 px-5 py-4 transition-colors hover:border-sand-400/50 hover:bg-white/5"
                >
                  <span className="font-medium text-cream">
                    {place.name} <span className="text-sand-300 transition-transform group-hover:translate-x-0.5">→</span>
                  </span>
                  <span className="mt-1 text-xs text-muted">{place.note}</span>
                </a>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
