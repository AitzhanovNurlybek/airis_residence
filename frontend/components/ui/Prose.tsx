import type { ReactNode } from "react";

/** Типографика текстовых страниц — без плагина, чтобы не тянуть лишнее. */
export function Prose({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`max-w-3xl text-[0.98rem] leading-[1.75] text-cream/80
        [&_a]:text-sand-300 [&_a]:underline [&_a]:underline-offset-4 hover:[&_a]:text-sand-200
        [&_h2]:mt-12 [&_h2]:mb-4 [&_h2]:font-display [&_h2]:text-2xl [&_h2]:font-semibold [&_h2]:text-cream md:[&_h2]:text-3xl
        [&_h3]:mt-8 [&_h3]:mb-3 [&_h3]:font-display [&_h3]:text-xl [&_h3]:text-cream
        [&_p]:my-4
        [&_ul]:my-5 [&_ul]:space-y-2.5 [&_ul]:pl-1
        [&_ol]:my-5 [&_ol]:list-decimal [&_ol]:space-y-2.5 [&_ol]:pl-6 [&_ol]:marker:text-sand-400
        [&_li]:pl-0
        [&_ul>li]:relative [&_ul>li]:pl-6
        [&_ul>li]:before:absolute [&_ul>li]:before:top-[0.7em] [&_ul>li]:before:left-0 [&_ul>li]:before:size-1.5 [&_ul>li]:before:rounded-full [&_ul>li]:before:bg-sand-400
        [&_strong]:font-semibold [&_strong]:text-cream
        [&_table]:my-6 [&_table]:w-full [&_table]:table-fixed [&_table]:border-collapse [&_table]:text-sm
        [&_th]:border-b [&_th]:border-white/12 [&_th]:py-3 [&_th]:pr-4 [&_th]:text-left [&_th]:text-xs [&_th]:tracking-[0.12em] [&_th]:text-sand-400 [&_th]:uppercase [&_th]:w-2/5
        [&_td]:border-b [&_td]:border-white/8 [&_td]:py-3 [&_td]:pr-4 [&_td]:align-top [&_td]:break-words
        ${className}`}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <header className="max-w-3xl">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="mt-4 font-display text-[clamp(2.1rem,4.6vw,3.4rem)] leading-[1.05] font-semibold text-cream">
        {title}
      </h1>
      {description && (
        <p className="mt-5 text-[1.02rem] leading-relaxed text-muted">{description}</p>
      )}
    </header>
  );
}
