/**
 * Каркас кабинета, пока грузятся данные компании.
 *
 * То же, что и в админке: сервер отвечает мгновенно, а данные идут из базы на
 * другом континенте. Светлый фон здесь, потому что кабинет светлый — каркас
 * должен быть похож на то, что появится, иначе он сам выглядит поломкой.
 */
function Line({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-ink-600/10 ${className}`} />;
}

export default function CorpLoading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Загружаем данные…</span>

      <div className="h-16 border-b border-white/8 bg-ink-950" />

      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <Line className="h-10 w-72" />
        <Line className="mt-5 h-16 w-full max-w-3xl" />

        <div className="mt-8 rounded-3xl bg-white p-6 shadow-sm md:p-8">
          <Line className="h-7 w-64" />
          <div className="mt-6 grid gap-x-10 gap-y-5 md:grid-cols-2">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i}>
                <Line className="h-3 w-24" />
                <Line className="mt-2 h-4 w-48" />
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 md:max-w-2xl">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-2xl bg-white px-6 py-5 shadow-sm">
              <Line className="h-8 w-24" />
              <Line className="mt-3 h-3 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
