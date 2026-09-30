import { LazyVideo } from "@/components/ui/LazyVideo";
import { getSiteVideos } from "@/lib/siteVideos";

/**
 * Видеообзоры отеля на главной: кухня, общие зоны.
 *
 * Роликов нет — секции нет вовсе, пустого заголовка не остаётся.
 * Ролики добавляются в админке, здесь ничего править не нужно.
 *
 * Блок — продолжение галереи, а не отдельный раздел: тот же фон, без
 * большого заголовка по центру. Раньше галерея, видео и 3D-тур шли тремя
 * самостоятельными разделами — три с половиной экрана подряд одного и того
 * же «посмотрите, как выглядит». Гость на этом месте уже поверил, что
 * отель настоящий, и ему нужна следующая ступень, а не третий заголовок.
 */
export async function VideoShowcase() {
  const videos = await getSiteVideos();
  if (videos.length === 0) return null;

  const single = videos.length === 1;

  const intro = (
    <div>
      <p className="eyebrow">Видео</p>
      <h2
        id="video-title"
        className="mt-3 font-display text-[clamp(1.5rem,3vw,2.2rem)] leading-tight text-cream"
      >
        Посмотрите, как здесь на самом деле
      </h2>
      <p className="mt-3 text-[0.95rem] leading-relaxed text-muted">
        Снято на телефон, без постановки и ретуши.
      </p>
    </div>
  );

  return (
    <section
      id="video"
      aria-labelledby="video-title"
      className="relative scroll-mt-24 bg-ink-900 pb-20 md:pb-28"
    >
      <div className="container-page">
        {single ? (
          // Один ролик: текст слева, ролик справа — одна строка вместо
          // заголовка по центру и плеера под ним.
          <div className="grid items-center gap-8 lg:grid-cols-[1fr_1.2fr] lg:gap-16">
            <div>
              {intro}
              <div className="mt-6 hidden border-l border-white/10 pl-5 lg:block">
                <h3 className="font-display text-xl text-cream">{videos[0].title}</h3>
                {videos[0].summary && (
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{videos[0].summary}</p>
                )}
              </div>
            </div>
            {/* По ширине кадра, а не колонки: ролики снимают и вертикально,
                и тогда в широкой рамке по бокам оставались чёрные поля. */}
            <figure className="lg:w-fit lg:justify-self-center">
              <LazyVideo
                src={videos[0].video}
                poster={videos[0].videoPoster || undefined}
                label={`Смотреть видео: ${videos[0].title}`}
              />
              <figcaption className="mt-4 lg:hidden">
                <h3 className="font-display text-xl text-cream">{videos[0].title}</h3>
                {videos[0].summary && (
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{videos[0].summary}</p>
                )}
              </figcaption>
            </figure>
          </div>
        ) : (
          <>
            {intro}
            <div className="mt-8 grid gap-10 sm:grid-cols-2 lg:grid-cols-3">
              {videos.map((item) => (
                <figure key={item.slug}>
                  <LazyVideo
                    src={item.video}
                    poster={item.videoPoster || undefined}
                    label={`Смотреть видео: ${item.title}`}
                  />
                  <figcaption className="mt-4">
                    <h3 className="font-display text-xl text-cream">{item.title}</h3>
                    {item.summary && (
                      <p className="mt-1.5 text-sm leading-relaxed text-muted">{item.summary}</p>
                    )}
                  </figcaption>
                </figure>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
