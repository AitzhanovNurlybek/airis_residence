/**
 * Воронка WhatsApp: докуда доходят гости, написавшие боту.
 *
 * Раздел отвечает на один вопрос — приносит бот деньги или просто вежливо
 * разговаривает. Поэтому здесь нет графиков и красивых карточек: три полосы
 * этапов, две цифры потерь и список разговоров, по которому можно позвонить.
 *
 * Список важнее процентов. По «29 % дошли до формы» сделать нельзя ничего,
 * а по строке «+7 708 724 14 60, довели до формы, молчит 4 часа» — можно.
 */

type Stage = { этап: string; сколько: number; доля: number };

type Talk = {
  телефон: string;
  этап: string;
  состояние: string;
  сообщений: number;
  "от гостя": number;
  "молчит часов": number;
  дожатий: number;
};

export type Funnel = {
  дней: number;
  разговоров: number;
  этапы: Stage[];
  потеряли_после_цен: number;
  потеряли_после_ссылки: number;
  молчат: number;
  ждут_ответа: number;
  дожали: number;
  спрашивали_фото: number;
  искали_свою_бронь: number;
  разговоры: Talk[];
};

const STATE_TONE: Record<string, string> = {
  "ждёт ответа": "border-wine-400/40 bg-wine-600/15 text-wine-100",
  идёт: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  молчит: "border-white/10 bg-white/5 text-muted",
};

function hours(n: number): string {
  if (n < 1) return "только что";
  if (n < 24) return `${n} ч`;
  const days = Math.round(n / 24);
  return `${days} дн`;
}

export function FunnelBoard({ data }: { data: Funnel }) {
  const { этапы: stages, разговоры: talks } = data;
  const waiting = talks.filter((t) => t.состояние === "ждёт ответа");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-3xl text-cream md:text-4xl">Воронка WhatsApp</h1>
        <p className="mt-1.5 text-sm text-muted">
          Докуда доходят гости, написавшие боту. За последние {data.дней} дней.
        </p>
      </div>

      {/* Гость, чьё сообщение осталось без ответа, — единственное, что требует
          действия прямо сейчас. Поэтому не в таблице, а наверху. */}
      {waiting.length > 0 && (
        <div
          role="alert"
          className="rounded-2xl border border-wine-400/40 bg-wine-600/15 px-5 py-4"
        >
          <p className="font-display text-lg text-wine-100">
            Ждут ответа: {waiting.length}
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-wine-100/85">
            {waiting.map((t) => t.телефон).join(", ")} — гость написал последним, и
            ответа не было.
          </p>
        </div>
      )}

      {data.разговоров === 0 ? (
        <p className="rounded-2xl border border-white/10 bg-white/5 px-5 py-8 text-center text-muted">
          За этот срок никто не писал.
        </p>
      ) : (
        <>
          <section className="rounded-2xl border border-white/10 bg-white/5 p-5 md:p-6">
            <ul className="space-y-4">
              {stages.map((stage) => (
                <li key={stage.этап}>
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="text-sm text-cream">{stage.этап}</span>
                    <span className="text-sm tabular-nums text-muted">
                      <b className="text-cream">{stage.сколько}</b> · {stage.доля}%
                    </span>
                  </div>
                  <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-sand-300"
                      style={{ width: `${stage.доля}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>

            <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-white/10 pt-5 text-sm md:grid-cols-4">
              {[
                ["Ушли после цен", data.потеряли_после_цен],
                ["Ушли после ссылки", data.потеряли_после_ссылки],
                ["Спрашивали фото", data.спрашивали_фото],
                ["Искали свою бронь", data.искали_свою_бронь],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-muted">{label}</dt>
                  <dd className="mt-0.5 font-display text-2xl text-cream tabular-nums">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="overflow-x-auto rounded-2xl border border-white/10 bg-white/5">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="border-b border-white/10 text-muted">
                <tr>
                  <th className="px-5 py-3 font-normal">Гость</th>
                  <th className="px-5 py-3 font-normal">Докуда дошёл</th>
                  <th className="px-5 py-3 font-normal">Сейчас</th>
                  <th className="px-5 py-3 font-normal text-right">Сообщений</th>
                  <th className="px-5 py-3 font-normal text-right">Молчит</th>
                </tr>
              </thead>
              <tbody>
                {talks.map((talk) => (
                  <tr key={talk.телефон} className="border-b border-white/5 last:border-0">
                    <td className="px-5 py-3">
                      <a
                        href={`https://wa.me/${talk.телефон.replace(/\D/g, "")}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-cream underline decoration-white/25 underline-offset-4 hover:decoration-cream"
                      >
                        {talk.телефон}
                      </a>
                      {talk.дожатий > 0 && (
                        <span className="ml-2 text-xs text-muted">
                          напомнили {talk.дожатий}×
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-cream">{talk.этап}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-block rounded-full border px-2.5 py-0.5 text-xs ${
                          STATE_TONE[talk.состояние] ?? STATE_TONE["молчит"]
                        }`}
                      >
                        {talk.состояние}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-muted">
                      {talk.сообщений}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-muted">
                      {talk.состояние === "молчит" ? hours(talk["молчит часов"]) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* Без этой оговорки воронку прочитают как «до брони дошли двое», а
              это не так: бронь оформляется в Exely, и связать её с перепиской
              не по чему — телефон Exely в ответах не отдаёт. */}
          <p className="text-sm leading-relaxed text-muted">
            Последний измеримый этап — «довели до формы». Дошёл ли гость до самой
            брони, здесь не видно: бронирование происходит в Exely, и связать бронь
            с перепиской нечем — телефон гостя Exely не отдаёт. Оформленные брони
            смотрите в кабинете Exely.
          </p>
        </>
      )}
    </div>
  );
}
