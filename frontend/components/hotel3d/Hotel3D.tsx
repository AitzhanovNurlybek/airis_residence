"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import points from "@/lib/hotel3d-points.json";

/**
 * Отель в 3D: вид сверху → «снимаем крышу» → этажи с номерами.
 *
 * Картинки и переходы сделаны по 3D-модели здания (3d/build_hotel.py —
 * поэтажные планы техпаспорта) и доведены до фотореализма в Higgsfield по
 * фото отеля. Кружки номеров посчитаны той же камерой модели
 * (3d/renders/hf/room_points.json), поэтому стоят над своими комнатами.
 *
 * Расположение категорий по этажам — ориентировочное: номера разложены по
 * площади из техпаспорта и количеству по этажам, которое назвал отель
 * (2026-11-24). Точный номер комнаты подтверждает стойка — так и написано
 * под схемой.
 */

export type Cat = "comfort_plus" | "comfort" | "standart" | "twin" | "single" | "apart";

export type CatInfo = {
  name: string;
  price: number | null;
  priceText: string;
  area: string;
  capacity: number;
  beds: string;
  summary: string;
  images: string[];
  video?: string;
  href?: string;
  bookHref: string;
};

type Point = { id: string; cat: Cat; x: number; y: number; area: number };
type View = "hotel" | 3 | 2 | 1;

const ORDER: View[] = ["hotel", 3, 2, 1];
const IMAGES: Record<string, string> = {
  "hotel-night": "/3d/hero-night.webp",
  "hotel-day": "/3d/hero-day.webp",
  "3": "/3d/floor-3.webp",
  "2": "/3d/floor-2.webp",
  "1": "/3d/floor-1.webp",
};
/** Переходы есть только сверху вниз: крыша уходит, этаж уходит. */
const TRANSITIONS: Record<string, string> = {
  "hotel>3": "/3d/roof-3.mp4",
  "3>2": "/3d/f3-f2.mp4",
  "2>1": "/3d/f2-f1.mp4",
};
export const CAT_COLOR: Record<Cat, string> = {
  comfort_plus: "#d98a2b",
  comfort: "#e9b44c",
  apart: "#d86a5f",
  standart: "#6b97d6",
  twin: "#55b277",
  single: "#a98bd6",
};
const CAT_ORDER: Cat[] = ["comfort_plus", "comfort", "apart", "standart", "twin", "single"];
const VIEW_LABEL: Record<string, string> = { hotel: "Здание", "3": "3 этаж", "2": "2 этаж", "1": "1 этаж" };

function imageKey(view: View, day: boolean) {
  return view === "hotel" ? (day ? "hotel-day" : "hotel-night") : String(view);
}

function prefersReducedMotion() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

export function Hotel3D({ cats }: { cats: Record<Cat, CatInfo> }) {
  const [view, setView] = useState<View>("hotel");
  const [day, setDay] = useState(false);
  const [queue, setQueue] = useState<string[]>([]);
  const [pending, setPending] = useState<View | null>(null);
  const [intro, setIntro] = useState(false);
  const [selected, setSelected] = useState<Point | null>(null);
  const [focusCat, setFocusCat] = useState<Cat | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const playing = queue.length > 0 || intro;

  // Вступление — один раз за визит: подлёт к отелю, кончается ровно на
  // вечернем кадре. Без анимаций (системная настройка) — сразу картинка.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let seen = false;
    try {
      seen = sessionStorage.getItem("airis3d-intro") === "1";
      sessionStorage.setItem("airis3d-intro", "1");
    } catch {
      /* без хранилища просто покажем вступление */
    }
    const v = videoRef.current;
    if (seen || !v) return;
    v.src = "/3d/intro.mp4";
    // Вступление показываем, только когда ролик действительно пошёл.
    v.play().then(() => setIntro(true)).catch(() => {});
  }, []);

  const go = useCallback(
    (target: View) => {
      if (playing || target === view) return;
      setSelected(null);
      const from = ORDER.indexOf(view);
      const to = ORDER.indexOf(target);
      // Переход играет по нажатию даже при «уменьшить анимацию»: человек сам
      // попросил показать этаж. Без спроса (вступление) — только без этой настройки.
      if (to < from) {
        setView(target);
        return;
      }
      const chain: string[] = [];
      for (let i = from; i < to; i += 1) {
        const src = TRANSITIONS[`${ORDER[i]}>${ORDER[i + 1]}`];
        if (src) chain.push(src);
      }
      if (!chain.length) {
        setView(target);
        return;
      }
      if (view === "hotel") setDay(false); // переходы сняты вечером
      // Тот же переход второй раз должен проиграться заново.
      videoRef.current?.removeAttribute("src");
      setPending(target);
      setQueue(chain);
    },
    [playing, view],
  );

  const onEnded = useCallback(() => {
    if (intro) {
      videoRef.current?.pause();
      setIntro(false);
      return;
    }
    const rest = queue.slice(1);
    setQueue(rest);
    if (!rest.length && pending !== null) {
      setView(pending);
      setPending(null);
    }
  }, [intro, queue, pending]);
  // Последняя версия обработчика — для эффекта ниже, чтобы смена очереди не
  // перезапускала уже играющий ролик.
  const endedRef = useRef(onEnded);
  useEffect(() => {
    endedRef.current = onEnded;
  }, [onEnded]);

  const src = intro ? "/3d/intro.mp4" : queue[0];
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !src || v.getAttribute("src") === src) return;
    v.src = src;
    v.currentTime = 0;
    // Автозапуск запрещён или файла нет — не зависаем, а идём дальше.
    v.play().catch(() => endedRef.current());
  }, [src]);

  const floorPoints = useMemo<Point[]>(
    () => (view === "hotel" ? [] : ((points as Record<string, Point[]>)[String(view)] ?? [])),
    [view],
  );
  const counts = useMemo(() => {
    const c: Partial<Record<Cat, number>> = {};
    for (const p of floorPoints) c[p.cat] = (c[p.cat] ?? 0) + 1;
    return c;
  }, [floorPoints]);

  const info = selected ? cats[selected.cat] : null;

  return (
    <div className="relative">
      <div className="relative">
      <div className="overflow-hidden rounded-card border border-white/8 bg-ink-900 shadow-deep">
        <div className="relative aspect-[1920/1086]">
          {Object.entries(IMAGES).map(([key, url]) => (
            <Image
              key={key}
              src={url}
              alt={key.startsWith("hotel") ? "Отель Airis Residence в Алматы, вид сверху" : `${key} этаж отеля Airis Residence, вид без крыши`}
              fill
              priority={key === "hotel-night"}
              sizes="(max-width: 1280px) 100vw, 1280px"
              className={`object-fill transition-opacity duration-700 ${
                imageKey(view, day) === key && !playing ? "opacity-100" : "opacity-0"
              }`}
            />
          ))}

          <video
            ref={videoRef}
            muted
            playsInline
            preload="auto"
            onEnded={() => endedRef.current()}
            onError={() => endedRef.current()}
            className={`absolute inset-0 h-full w-full object-fill transition-opacity duration-300 ${
              playing ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
          />

          {intro && (
            <button
              type="button"
              onClick={onEnded}
              className="absolute bottom-4 left-4 rounded-full border border-white/20 bg-ink-950/60 px-4 py-2 text-xs text-cream backdrop-blur-md"
            >
              Пропустить
            </button>
          )}

          {/* Номера на этаже */}
          {!playing &&
            floorPoints.map((p) => {
              const dim = focusCat && focusCat !== p.cat;
              const c = cats[p.cat];
              return (
                <button
                  key={p.id}
                  type="button"
                  aria-label={`${c.name}${c.priceText ? `, ${c.priceText}` : ""}`}
                  onClick={() => setSelected(p)}
                  onMouseEnter={() => setHover(p.id)}
                  onMouseLeave={() => setHover(null)}
                  style={{ left: `${p.x}%`, top: `${p.y}%`, ["--c" as string]: CAT_COLOR[p.cat] }}
                  className={`group absolute z-10 -translate-x-1/2 -translate-y-1/2 transition-opacity duration-300 ${
                    dim ? "opacity-25" : "opacity-100"
                  }`}
                >
                  <span className="absolute inset-0 animate-ping rounded-full bg-[var(--c)] opacity-30" />
                  <span className="relative block h-3.5 w-3.5 rounded-full border-2 border-white bg-[var(--c)] shadow-[0_2px_10px_rgba(0,0,0,0.5)] transition-transform group-hover:scale-125 md:h-6 md:w-6" />
                  {hover === p.id && (
                    <span className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 whitespace-nowrap rounded-xl border border-white/15 bg-ink-950/90 px-3 py-2 text-left text-xs text-cream shadow-lift backdrop-blur-md">
                      <span className="block font-semibold">{c.name}</span>
                      {c.priceText && <span className="block text-sand-200">{c.priceText}</span>}
                    </span>
                  )}
                </button>
              );
            })}

          {/* День / вечер — только на виде здания */}
          {view === "hotel" && !playing && (
            <div className="absolute top-2 left-2 z-20 flex rounded-full border border-white/15 bg-ink-950/55 p-0.5 text-[0.65rem] backdrop-blur-md md:top-4 md:left-4 md:p-1 md:text-xs">
              {[
                { d: false, label: "Вечер" },
                { d: true, label: "День" },
              ].map((o) => (
                <button
                  key={o.label}
                  type="button"
                  onClick={() => setDay(o.d)}
                  className={`rounded-full px-2.5 py-1 transition-colors md:px-3.5 md:py-1.5 ${
                    day === o.d ? "bg-sand-300 text-ink-950" : "text-cream/80 hover:text-cream"
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}

          {view === "hotel" && !playing && (
            <button
              type="button"
              onClick={() => go(3)}
              className="absolute bottom-3 left-1/2 z-20 -translate-x-1/2 rounded-full bg-sand-300 px-4 py-2 text-xs font-medium text-ink-950 shadow-lift transition-transform hover:scale-[1.03] md:bottom-5 md:px-6 md:py-3 md:text-sm"
            >
              Заглянуть внутрь
            </button>
          )}
        </div>
      </div>

          {/* Этажи */}
      <nav
        aria-label="Этажи отеля"
        className="mt-3 flex justify-center gap-2 md:absolute md:top-1/2 md:right-4 md:z-20 md:mt-0 md:-translate-y-1/2 md:flex-col"
      >
        {ORDER.map((v) => (
          <button
            key={String(v)}
            type="button"
            disabled={playing}
            onClick={() => go(v)}
            className={`rounded-full border px-3 py-2 text-xs md:min-w-[5.5rem] md:px-4 backdrop-blur-md transition-colors disabled:opacity-60 ${
              view === v
                ? "border-sand-300 bg-sand-300 text-ink-950"
                : "border-white/15 bg-ink-950/55 text-cream/85 hover:border-sand-300/60 hover:text-cream"
            }`}
          >
            {VIEW_LABEL[String(v)]}
          </button>
        ))}
      </nav>
      </div>

      {/* Легенда */}
      <div className="mt-5 flex flex-wrap gap-2">
        {CAT_ORDER.filter((k) => view === "hotel" || counts[k]).map((k) => (
          <button
            key={k}
            type="button"
            onMouseEnter={() => setFocusCat(k)}
            onMouseLeave={() => setFocusCat(null)}
            onClick={() => setFocusCat((f) => (f === k ? null : k))}
            className={`flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs transition-colors ${
              focusCat === k ? "border-white/40 bg-white/10" : "border-white/10 bg-ink-800 hover:border-white/25"
            }`}
          >
            <span className="h-3 w-3 rounded-full" style={{ background: CAT_COLOR[k] }} />
            <span className="text-cream">{cats[k].name}</span>
            {cats[k].priceText && <span className="text-muted">{cats[k].priceText}</span>}
            {view !== "hotel" && counts[k] ? <span className="text-muted">· {counts[k]}</span> : null}
          </button>
        ))}
      </div>

      {/* Карточка номера */}
      {info && selected && (
        <div className="fixed inset-0 z-[60] flex justify-end bg-ink-950/60 backdrop-blur-sm" onClick={() => setSelected(null)}>
          <aside
            role="dialog"
            aria-label={info.name}
            onClick={(e) => e.stopPropagation()}
            className="mt-auto max-h-[88vh] w-full overflow-y-auto rounded-t-card border border-white/10 bg-ink-900 md:mt-0 md:h-full md:max-h-none md:max-w-md md:rounded-none md:border-y-0 md:border-r-0"
          >
            <RoomPanel info={info} color={CAT_COLOR[selected.cat]} floor={view} onClose={() => setSelected(null)} />
          </aside>
        </div>
      )}
    </div>
  );
}

function RoomPanel({ info, color, floor, onClose }: { info: CatInfo; color: string; floor: View; onClose: () => void }) {
  const [i, setI] = useState(0);
  return (
    <div className="flex min-h-full flex-col">
      <div className="relative aspect-4/3 w-full bg-ink-800">
        {info.images.length > 0 ? (
          <Image src={info.images[i]} alt={info.name} fill sizes="(max-width: 768px) 100vw, 448px" className="object-cover" />
        ) : info.video ? (
          <video src={info.video} controls muted playsInline className="h-full w-full object-cover" />
        ) : null}
        <button
          type="button"
          onClick={onClose}
          aria-label="Закрыть"
          className="absolute top-3 right-3 flex h-9 w-9 items-center justify-center rounded-full bg-ink-950/70 text-lg text-cream backdrop-blur-md"
        >
          ×
        </button>
      </div>
      {info.images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto px-5 pt-3">
          {info.images.slice(0, 6).map((src, k) => (
            <button
              key={src}
              type="button"
              onClick={() => setI(k)}
              className={`relative h-14 w-20 shrink-0 overflow-hidden rounded-lg border ${k === i ? "border-sand-300" : "border-white/10"}`}
            >
              <Image src={src} alt="" fill sizes="80px" className="object-cover" />
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-1 flex-col p-5 md:p-6">
        <p className="flex items-center gap-2 text-[0.7rem] tracking-[0.14em] text-muted uppercase">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          {floor === "hotel" ? "" : `${floor} этаж`}
        </p>
        <h3 className="mt-2 font-display text-2xl text-cream">{info.name}</h3>
        <p className="mt-2 text-sm text-muted">
          {[info.area, `до ${info.capacity} ${info.capacity === 1 ? "гостя" : "гостей"}`, info.beds].filter(Boolean).join(" · ")}
        </p>
        {info.summary && <p className="mt-4 text-sm leading-relaxed text-cream/85">{info.summary}</p>}
        <div className="mt-auto pt-6">
          {info.priceText && <p className="font-display text-2xl text-sand-200">{info.priceText}</p>}
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href={info.bookHref}
              className="rounded-full bg-sand-300 px-5 py-3 text-sm font-medium text-ink-950 transition-transform hover:scale-[1.03]"
            >
              Забронировать
            </a>
            {info.href && (
              <Link
                href={info.href}
                className="rounded-full border border-white/15 px-5 py-3 text-sm text-cream/85 hover:border-sand-300/50"
              >
                Подробнее о номере
              </Link>
            )}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-muted">
            Расположение номеров на схеме ориентировочное. Номер комнаты назначает стойка при заселении.
          </p>
        </div>
      </div>
    </div>
  );
}
