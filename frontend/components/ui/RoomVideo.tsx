import { LazyVideo } from "@/components/ui/LazyVideo";

/** Видеообзор на странице номера. Сам плеер — в LazyVideo. */
export function RoomVideo({
  src,
  poster,
  name,
}: {
  src: string;
  poster?: string;
  name: string;
}) {
  return (
    <section className="mt-16">
      <h2 className="font-display text-2xl text-cream">Видеообзор номера</h2>
      <p className="mt-2 text-sm text-muted">
        Как всё выглядит на самом деле — без ретуши и удачных ракурсов.
      </p>

      <LazyVideo
        src={src}
        poster={poster}
        label={`Смотреть видеообзор номера ${name}`}
        className="mt-6"
      />
    </section>
  );
}
