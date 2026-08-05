/* eslint-disable @next/next/no-img-element */

/**
 * Превью фотографии в админке.
 *
 * Здесь намеренно обычный <img>, а не next/image: в админку попадают
 * ссылки и на локальные файлы, и на бэкенд, и оптимизировать их
 * незачем — это внутренний инструмент на пару человек. На публичном
 * сайте фотографии по-прежнему идут через next/image.
 */
export function AdminThumb({
  src,
  alt,
  className = "",
}: {
  src?: string;
  alt: string;
  className?: string;
}) {
  return (
    <div
      className={`relative aspect-4/3 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-ink-800 ${className}`}
    >
      {src ? (
        <img src={src} alt={alt} loading="lazy" className="size-full object-cover" />
      ) : (
        <span className="grid size-full place-items-center text-[0.65rem] text-muted">
          нет фото
        </span>
      )}
    </div>
  );
}
