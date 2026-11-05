import { LazyVideo } from "@/components/ui/LazyVideo";
import type { Lang } from "@/lib/routes";

/** Видеообзор на странице номера. Сам плеер — в LazyVideo. */
export function RoomVideo({
  src,
  poster,
  name,
  lang = "ru",
}: {
  src: string;
  poster?: string;
  name: string;
  lang?: Lang;
}) {
  const en = lang === "en";
  return (
    <section className="mt-16">
      <h2 className="font-display text-2xl text-cream">{en ? "Room video tour" : "Видеообзор номера"}</h2>
      <p className="mt-2 text-sm text-muted">
        {en
          ? "What it really looks like — no retouching, no flattering angles."
          : "Как всё выглядит на самом деле — без ретуши и удачных ракурсов."}
      </p>

      <LazyVideo
        src={src}
        poster={poster}
        label={en ? `Watch the video tour of the ${name} room` : `Смотреть видеообзор номера ${name}`}
        className="mt-6"
      />
    </section>
  );
}
