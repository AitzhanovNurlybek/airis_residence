import { Reveal } from "@/components/ui/Reveal";
import { eventVenues } from "@/lib/site";

/**
 * Событийный крючок для туристов — сразу под первым экраном.
 *
 * Гость, который летит в Алматы на концерт или матч, выбирает отель по одному
 * признаку: сколько добираться до площадки в день события, когда центр стоит
 * в пробках и такси не поймать. Поэтому блок отвечает ровно на этот вопрос и
 * стоит выше рассказа об отеле — до него доскроллит уже заинтересованный.
 *
 * Названия событий даны с датами. Соблазн написать «здесь выступают мировые
 * звёзды» велик, но это пустая фраза: её пишут все. Проверяемый факт с числом
 * работает лучше и, в отличие от обещания, не может оказаться неправдой.
 */
export function EventsNearby() {
  return (
    <section
      aria-labelledby="sobytiya-title"
      className="border-y border-white/8 bg-ink-900/40"
    >
      <div className="container-page py-14 md:py-16">
        <Reveal>
          <p className="eyebrow">Событийный центр города</p>
          <h2
            id="sobytiya-title"
            className="mt-4 max-w-3xl font-display text-[clamp(1.6rem,3.2vw,2.3rem)] leading-[1.15] font-semibold text-cream"
          >
            До больших концертов и матчей — пешком
          </h2>
          <p className="mt-4 max-w-2xl text-[1.02rem] leading-relaxed text-muted">
            Главные площадки Алматы стоят в соседних кварталах. В день события,
            когда центр забит и такси не поймать, до стадиона можно дойти
            за двадцать минут.
          </p>
        </Reveal>

        <ul className="mt-10 grid gap-5 md:grid-cols-3">
          {eventVenues.map((venue, index) => (
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

        <p className="mt-8 text-xs leading-relaxed text-muted">
          Расстояния — пешком по улицам, а не по прямой. Афишу площадок стоит
          сверять перед поездкой: даты меняются.
        </p>
      </div>
    </section>
  );
}
