import { airport, type AirportOption, type AirportStep } from "@/lib/site";
import { Reveal } from "@/components/ui/Reveal";
import { buttonClass } from "@/components/ui/Button";
import {
  IconArrow,
  IconBus,
  IconMoon,
  IconPin,
  IconPlane,
  IconTransfer,
  IconTrolley,
  IconWalk,
  IconWhatsApp,
} from "@/components/ui/Icons";

/**
 * Как добраться из аэропорта.
 *
 * Блок для туристов: многие приезжают автобусом и хотят понять маршрут до
 * того, как сядут в самолёт. Поэтому у каждого варианта не абзац текста, а
 * полоска пути — пешком, какой автобус, где пересадка, — как её рисуют сами
 * навигаторы. Такая схема читается с одного взгляда и переводится Google
 * Translate без потерь: номера маршрутов не переводятся, а подписи короткие.
 *
 * Карты с нарисованным маршрутом здесь намеренно нет. Схема в картинке
 * устаревает молча, как только город меняет маршрут, а кнопки внизу ведут в
 * живой маршрут — на языке гостя и с сегодняшним расписанием.
 */

const optionIcon: Record<string, (p: { className?: string }) => React.ReactElement> = {
  transfer: IconTransfer,
  taxi: IconTransfer,
  "bus-96": IconBus,
  "bus-120": IconBus,
  "bus-3-night": IconMoon,
};

function describeSteps(steps: readonly AirportStep[]): string {
  return steps
    .map((step) =>
      step.kind === "walk"
        ? `пешком ${step.minutes} минут`
        : `${step.kind === "bus" ? "автобус" : "троллейбус"} ${step.lines.join(" или ")}`,
    )
    .join(", затем ");
}

function RouteStrip({ steps }: { steps: readonly AirportStep[] }) {
  return (
    <ol
      className="mt-4 flex flex-wrap items-center gap-y-2"
      aria-label={describeSteps(steps)}
    >
      {steps.map((step, index) => (
        <li key={index} className="flex items-center">
          {step.kind === "walk" && (
            <span className="inline-flex items-center gap-1 text-xs text-muted">
              <IconWalk className="size-4" />
              {step.minutes} мин
            </span>
          )}
          {step.kind === "bus" && (
            <span className="inline-flex items-center gap-1 rounded-md bg-sand-400 px-2 py-1 text-xs font-semibold text-ink-950 tabular-nums">
              <IconBus className="size-3.5" />
              {step.lines.join(" · ")}
            </span>
          )}
          {step.kind === "trolley" && (
            <span className="inline-flex items-center gap-1 rounded-md border border-sand-400/60 px-2 py-1 text-xs font-semibold text-sand-200 tabular-nums">
              <IconTrolley className="size-3.5" />
              {step.lines.join(" / ")}
            </span>
          )}
          {index < steps.length - 1 && (
            <span aria-hidden className="mx-0.5 h-px w-2 bg-white/20 sm:mx-1.5 sm:w-6" />
          )}
        </li>
      ))}
    </ol>
  );
}

function OptionCard({ option }: { option: AirportOption }) {
  const Icon = optionIcon[option.id] ?? IconTransfer;
  return (
    <li className="rounded-2xl border border-white/8 bg-ink-950/40 p-5">
      <div className="flex gap-4">
        <span className="hidden size-10 shrink-0 items-center justify-center rounded-full border border-sand-400/30 text-sand-400 sm:flex">
          <Icon className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h4 className="text-[0.95rem] font-medium text-cream">{option.title}</h4>
            <span className="text-sm text-sand-400 tabular-nums">{option.price}</span>
          </div>
          <p className="mt-1 text-xs text-muted">{option.time}</p>
          {option.steps && <RouteStrip steps={option.steps} />}
          <p className="mt-3 text-sm leading-relaxed text-cream/70">{option.note}</p>
          {option.id === "transfer" && (
            <a
              href={airport.transferWhatsapp}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonClass("outline", "md", "mt-4 h-10 px-5")}
            >
              <IconWhatsApp className="size-4" />
              Написать о трансфере
            </a>
          )}
        </div>
      </div>
    </li>
  );
}

function Group({ title, options }: { title: string; options: readonly AirportOption[] }) {
  return (
    <div>
      <h4 className="eyebrow">{title}</h4>
      <ul className="mt-4 space-y-3">
        {options.map((option) => (
          <OptionCard key={option.id} option={option} />
        ))}
      </ul>
    </div>
  );
}

export function AirportRoutes() {
  const car = airport.options.filter((option) => option.group === "car");
  const bus = airport.options.filter((option) => option.group === "bus");

  return (
    <div id="iz-aeroporta" className="mt-16 scroll-mt-24 md:mt-24">
      <Reveal>
        <div className="rounded-card border border-white/10 bg-ink-900 p-6 md:p-10">
          <p className="eyebrow">Из аэропорта</p>
          <h3 className="mt-3 font-display text-2xl leading-tight font-semibold text-cream md:text-3xl">
            Как добраться до отеля
          </h3>

          {/* Путь одной линией: откуда, сколько, куда. Первое, что хочет
              понять человек после посадки, — насколько это далеко. */}
          <div className="mt-8 flex items-center gap-3 md:gap-5">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-sand-400 text-ink-950">
              <IconPlane className="size-5" />
            </span>
            <span className="hidden shrink-0 text-sm sm:block">
              <span className="block text-cream">Аэропорт</span>
              <span className="block text-xs text-muted">{airport.code}</span>
            </span>
            <span className="relative flex-1">
              <span aria-hidden className="block border-t border-dashed border-sand-400/45" />
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-ink-900 px-3 text-sm whitespace-nowrap text-sand-300 tabular-nums">
                {airport.distance}
              </span>
            </span>
            <span className="hidden shrink-0 text-right text-sm sm:block">
              <span className="block text-cream">Airis Residence</span>
              <span className="block text-xs text-muted">Алмалинский район</span>
            </span>
            <span className="flex size-11 shrink-0 items-center justify-center rounded-full border border-sand-400/50 text-sand-300">
              <IconPin className="size-5" />
            </span>
          </div>
          {/* На телефоне подписи не помещаются рядом с линией и обрезались на
              полуслове («Аэропор»). Здесь им хватает всей ширины. */}
          <div className="mt-2 flex justify-between text-xs sm:hidden">
            <span>
              <span className="block text-cream">Аэропорт {airport.code}</span>
            </span>
            <span className="text-right">
              <span className="block text-cream">Airis Residence</span>
            </span>
          </div>

          <div className="mt-10 grid gap-8 lg:grid-cols-2 lg:gap-10">
            <Group title="На машине" options={car} />
            <Group title="На общественном транспорте" options={bus} />
          </div>

          <p className="mt-8 text-sm leading-relaxed text-cream/70">{airport.payment}</p>

          <div className="mt-6 flex flex-wrap gap-3">
            <a
              href={airport.routeGoogle}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonClass("primary", "md")}
            >
              Маршрут в Google Maps
              <IconArrow className="size-4" />
            </a>
            <a
              href={airport.route2gis}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonClass("outline", "md")}
            >
              Открыть в 2ГИС
            </a>
          </div>

          <p className="mt-5 text-xs leading-relaxed text-muted">
            Маршруты — по данным 2ГИС до адреса отеля, сентябрь 2026. Время и интервалы
            примерные: точное расписание на сегодня покажет приложение.
          </p>
        </div>
      </Reveal>
    </div>
  );
}
