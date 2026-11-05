import { Reveal } from "@/components/ui/Reveal";
import { eventVenues } from "@/lib/site";
import { eventVenuesEn } from "@/lib/en";
import type { Lang } from "@/lib/routes";

const T = {
  ru: {
    eyebrow: "Событийный центр города",
    title: "До больших концертов и матчей — пешком",
    text: "Главные площадки Алматы стоят в соседних кварталах. В день события, когда центр забит и такси не поймать, до стадиона можно дойти за двадцать минут.",
    note: "Расстояния — пешком по улицам, а не по прямой. Афишу площадок стоит сверять перед поездкой: даты меняются.",
  },
  en: {
    eyebrow: "Events in the city",
    title: "Walk to big concerts and matches",
    text: "Almaty's main venues are a few blocks away. On event day, when the centre is jammed and taxis are hard to get, you can walk to the stadium in about twenty minutes.",
    note: "Distances are walking distances along the streets, not straight lines. Check the venues' schedules before your trip — dates change.",
  },
} as const;

/**
 * Событийный крючок для туристов — сразу под картой.
 *
 * Гость, который летит в Алматы на концерт или матч, выбирает отель по одному
 * признаку: сколько добираться до площадки в день события, когда центр стоит
 * в пробках и такси не поймать. Блок отвечает ровно на этот вопрос.
 *
 * Сначала он стоял сразу под первым экраном, выше номеров. Но такой гость —
 * часть посетителей, а номера с ценой нужны всем: на телефоне из-за этого
 * блока и рассказа об отеле номера начинались только с 4-го экрана. Под
 * картой он там, где гость и так смотрит «что рядом», а стадион с театром
 * тогда убираются из списка «Рядом с отелем», чтобы не повторяться.
 *
 * Названия событий даны с датами. Соблазн написать «здесь выступают мировые
 * звёзды» велик, но это пустая фраза: её пишут все. Проверяемый факт с числом
 * работает лучше и, в отличие от обещания, не может оказаться неправдой.
 */
export function EventsNearby({ lang = "ru" }: { lang?: Lang }) {
  const t = T[lang];
  const venues = lang === "en" ? eventVenuesEn : eventVenues;
  return (
    <section
      aria-labelledby="sobytiya-title"
      className="border-y border-white/8 bg-ink-900/40"
    >
      <div className="container-page py-14 md:py-16">
        <Reveal>
          <p className="eyebrow">{t.eyebrow}</p>
          <h2
            id="sobytiya-title"
            className="mt-4 max-w-3xl font-display text-[clamp(1.6rem,3.2vw,2.3rem)] leading-[1.15] font-semibold text-cream"
          >
            {t.title}
          </h2>
          <p className="mt-4 max-w-2xl text-[1.02rem] leading-relaxed text-muted">{t.text}</p>
        </Reveal>

        <ul className="mt-10 grid gap-5 md:grid-cols-3">
          {venues.map((venue, index) => (
            <Reveal key={venue.name} delay={0.05 * index}>
              <li className="h-full rounded-2xl border border-white/10 bg-ink-950/50 p-6">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="font-display text-lg text-cream">{venue.name}</h3>
                </div>
                <p className="mt-1.5 text-xs tracking-wide text-sand-400">{venue.walk}</p>
                <p className="mt-4 text-sm leading-relaxed text-muted">{venue.note}</p>

                <ul className="mt-4 space-y-2 border-t border-white/8 pt-4">
                  {venue.highlights.map((line) => (
                    <li key={line} className="text-sm leading-snug text-cream/80">
                      {line}
                    </li>
                  ))}
                </ul>
              </li>
            </Reveal>
          ))}
        </ul>

        <p className="mt-8 text-xs leading-relaxed text-muted">{t.note}</p>
      </div>
    </section>
  );
}
