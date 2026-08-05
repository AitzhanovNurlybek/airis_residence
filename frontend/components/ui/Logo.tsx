/**
 * Логотипа у отеля нет — собран словесный знак (логотип-надпись).
 * Монограмма: арка «A» с точкой — отсылка к дверному проёму и к букве A.
 * Если появится готовый логотип, заменить только этот компонент.
 */
export function Logo({
  className = "",
  withMark = true,
}: {
  className?: string;
  withMark?: boolean;
}) {
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      {withMark && (
        <svg
          viewBox="0 0 40 40"
          className="h-full w-auto shrink-0"
          fill="none"
          aria-hidden
        >
          <path
            d="M20 3.5c-8 0-14 6-14 14V36"
            stroke="url(#airis-mark)"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
          <path
            d="M20 3.5c8 0 14 6 14 14V36"
            stroke="url(#airis-mark)"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
          <path d="M11.5 25.5h17" stroke="url(#airis-mark)" strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="20" cy="14" r="2.2" fill="currentColor" className="text-wine-400" />
          <defs>
            <linearGradient id="airis-mark" x1="20" y1="3.5" x2="20" y2="36" gradientUnits="userSpaceOnUse">
              <stop stopColor="#e8dcc8" />
              <stop offset="1" stopColor="#ad8d5b" />
            </linearGradient>
          </defs>
        </svg>
      )}
      <span className="flex flex-col justify-center leading-none">
        <span className="font-display text-[1.35em] leading-[1] font-semibold tracking-[0.14em] text-cream">
          AIRIS
        </span>
        <span className="mt-[0.25em] text-[0.5em] leading-[1] font-medium tracking-[0.42em] text-sand-400">
          RESIDENCE
        </span>
      </span>
    </span>
  );
}
