import { SectionHead } from "@/components/ui/SectionHead";
import { LazyVideo } from "@/components/ui/LazyVideo";
import { getSiteVideos } from "@/lib/siteVideos";

/**
 * Видеообзоры отеля на главной: кухня, общие зоны.
 *
 * Роликов нет — секции нет вовсе, пустого заголовка не остаётся.
 * Ролики добавляются в админке, здесь ничего править не нужно.
 */
export async function VideoShowcase() {
  const videos = await getSiteVideos();
  if (videos.length === 0) return null;

  const single = videos.length === 1;

  return (
    <section id="video" className="relative scroll-mt-24 py-20 md:py-32">
      <div className="container-page">
        <SectionHead
          eyebrow="Видео"
          title="Посмотрите, как здесь на самом деле"
          description="Снято на телефон, без постановки и ретуши."
          align="center"
        />

        <div
          className={
            single ? "mt-10 md:mt-14" : "mt-10 grid gap-10 sm:grid-cols-2 md:mt-14 lg:grid-cols-3"
          }
        >
          {videos.map((item) => (
            <figure key={item.slug} className={single ? "mx-auto max-w-2xl" : ""}>
              <LazyVideo
                src={item.video}
                poster={item.videoPoster || undefined}
                label={`Смотреть видео: ${item.title}`}
              />
              <figcaption className={`mt-4 ${single ? "text-center" : ""}`}>
                <h3 className="font-display text-xl text-cream">{item.title}</h3>
                {item.summary && (
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{item.summary}</p>
                )}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
