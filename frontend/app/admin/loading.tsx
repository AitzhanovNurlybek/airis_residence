/**
 * Каркас, пока грузятся данные админки.
 *
 * Сервер отдаёт страницу за 87 миллисекунд, но данные приезжают из базы в
 * Сиднее ещё пару секунд — и всё это время менеджер смотрел в пустой экран,
 * не понимая, работает ли вообще.
 *
 * Быстрее данные от этого не станут: расстояние никуда не денется. Но пустота
 * ощущается дольше, чем такой же по длине показ каркаса, — человек видит, что
 * страница открылась, и знает, чего ждать.
 */
function Line({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-white/6 ${className}`} />;
}

export default function AdminLoading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Загружаем данные…</span>

      <Line className="h-9 w-56" />
      <Line className="mt-4 h-4 w-full max-w-xl" />

      <div className="mt-8 grid gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-2xl border border-white/8 bg-ink-900/40 p-5"
            style={{ animationDelay: `${i * 90}ms` }}
          >
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0 flex-1">
                <Line className="h-5 w-48" />
                <Line className="mt-3 h-3.5 w-64" />
                <Line className="mt-2 h-3.5 w-40" />
              </div>
              <Line className="h-10 w-32 shrink-0" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
