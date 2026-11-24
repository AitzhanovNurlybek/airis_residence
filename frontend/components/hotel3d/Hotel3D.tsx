"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import points from "@/lib/hotel3d-points.json";

import { ASSISTANT_NAME, ReceptionChat } from "./ReceptionChat";

/**
 * Отель в 3D: здание → «снимаем крышу» → этажи → заходим в номер.
 *
 * Здание и этажи — 3D-модель по поэтажным планам техпаспорта
 * (3d/build_hotel.py), доведённая до фотореализма в Higgsfield. Номера
 * внутри — по реальным фото каждой категории, расширенным до широкого кадра.
 * Всё снято в двух вариантах, «вечер» и «день», кадр в кадр, поэтому время
 * суток переключается плавным наплывом на любом шаге.
 *
 * Ролик «вход в номер» сгенерирован как отъезд камеры из номера в коридор и
 * развёрнут задом наперёд (ffmpeg reverse): так он кончается ровно на кадре
 * номера и переход в картинку бесшовный.
 *
 * Скорость: сразу грузится только первый кадр. Остальное подгружается по
 * ходу — следующий этаж заранее, номер по нажатию (пока идёт ролик). Кружки
 * без бесконечной анимации и без размытия фона: на слабых телефонах именно
 * это давало подтормаживание.
 *
 * Расположение категорий по этажам — ориентировочное: номера разложены по
 * площади из техпаспорта и количеству по этажам, которое назвал отель
 * (2026-11-24). Точный номер комнаты подтверждает стойка — так и написано.
 */

export type Cat =
  "comfort_plus" | "comfort" | "standart" | "twin" | "single" | "apart";

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
type Floor = 1 | 2 | 3;
type View = "hotel" | Floor | "lobby";
type Spot = { x: number; y: number };
type Tod = "eve" | "day";
type Step = { src: string; then?: () => void };

const ORDER: View[] = ["hotel", 3, 2, 1];
/** Переходы есть только сверху вниз: крыша уходит, этаж уходит. */
const TRANSITIONS: Record<Tod, Record<string, string>> = {
  eve: {
    "hotel>3": "/3d/roof-3.mp4",
    "3>2": "/3d/f3-f2.mp4",
    "2>1": "/3d/f2-f1.mp4",
  },
  day: {
    "hotel>3": "/3d/roof-3-day.mp4",
    "3>2": "/3d/f3-f2-day.mp4",
    "2>1": "/3d/f2-f1-day.mp4",
  },
};
export const CAT_COLOR: Record<Cat, string> = {
  comfort_plus: "#d98a2b",
  comfort: "#e9b44c",
  apart: "#d86a5f",
  standart: "#6b97d6",
  twin: "#55b277",
  single: "#a98bd6",
};
const CAT_ORDER: Cat[] = [
  "comfort_plus",
  "comfort",
  "apart",
  "standart",
  "twin",
  "single",
];
const VIEW_LABEL: Record<string, string> = {
  lobby: "Ресепшн",
  hotel: "Здание",
  "3": "3 этаж",
  "2": "2 этаж",
  "1": "1 этаж",
};
/** Кнопки снизу/сбоку: ресепшн отдельно от этажей (он не в цепочке крыши). */
const NAV: View[] = ["lobby", "hotel", 3, 2, 1];
/** Входные двери лобби на виде сверху (hero-night/day, кадр в кадр). */
const ENTRANCE: Spot = { x: 52.5, y: 76 };
/** Наезд камеры на номер перед роликом входа. */
const ZOOM = 2.6;
const ZOOM_MS = 800;
const IMG_SIZES = "(max-width: 1280px) 100vw, 1280px";

const slug = (cat: Cat) => cat.replace("_", "-");

/** Кадр: hotel:<tod> · lobby:<tod> · floor:<n>:<tod> · room:<slug>:<tod>. */
function keyOf(view: View, room: Point | null, tod: Tod) {
  if (room) return `room:${slug(room.cat)}:${tod}`;
  if (view === "lobby") return `lobby:${tod}`;
  return view === "hotel" ? `hotel:${tod}` : `floor:${view}:${tod}`;
}

/** Путь к кадру без расширения: рядом лежат .webp (1920) и -960.webp. */
function basePath(key: string) {
  const [kind, a, b] = key.split(":");
  if (kind === "hotel") return a === "day" ? "/3d/hero-day" : "/3d/hero-night";
  if (kind === "lobby") return `/3d/reception-${a}`;
  if (kind === "floor")
    return b === "day" ? `/3d/floor-${a}-day` : `/3d/floor-${a}`;
  return `/3d/rooms/${a}-${b}`;
}

function altOf(key: string) {
  const [kind, a] = key.split(":");
  if (kind === "hotel") return "Отель Airis Residence в Алматы, вид сверху";
  if (kind === "lobby")
    return `Стойка регистрации Airis Residence, администратор ${ASSISTANT_NAME}`;
  if (kind === "floor") return `${a} этаж отеля Airis Residence, вид без крыши`;
  return "Номер отеля Airis Residence внутри";
}

/** Дождаться, пока кадр скачан и разжат, — чтобы наплыв не мигал пустотой. */
function ready(key: string): Promise<void> {
  const b = basePath(key);
  const img = new window.Image();
  img.sizes = IMG_SIZES;
  img.srcset = `${b}-960.webp 960w, ${b}.webp 1920w`;
  img.src = `${b}.webp`;
  return img.decode().catch(() => undefined);
}

function prefersReducedMotion() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

export function Hotel3D({
  cats,
  intro: withIntro = true,
}: {
  cats: Record<Cat, CatInfo>;
  /** Вступительный облёт. На главной его не надо: он и так идёт в первом экране. */
  intro?: boolean;
}) {
  const [view, setView] = useState<View>("hotel");
  const [tod, setTod] = useState<Tod>("eve");
  const [room, setRoom] = useState<Point | null>(null);
  const [zoom, setZoom] = useState<Spot | null>(null);
  const [back, setBack] = useState<{ p: Spot; n: number } | null>(null);
  const [mounted, setMounted] = useState<string[]>(["hotel:eve"]);
  const [busy, setBusy] = useState(false);
  const [videoOn, setVideoOn] = useState(false);
  const [intro, setIntro] = useState(false);
  const [photos, setPhotos] = useState(false);
  const [focusCat, setFocusCat] = useState<Cat | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const chain = useRef<{ steps: Step[]; current?: Step } | null>(null);
  const started = useRef(false);

  const current = keyOf(view, room, tod);

  function need(...keys: string[]) {
    setMounted((m) => {
      const add = keys.filter((k) => !m.includes(k));
      return add.length ? [...m, ...add] : m;
    });
  }

  // ── Ролики: вступление, переходы между этажами, вход в номер ──────────
  function next() {
    const c = chain.current;
    if (!c) return;
    c.current?.then?.();
    const step = c.steps.shift();
    c.current = step;
    if (!step) {
      chain.current = null;
      setVideoOn(false);
      setBusy(false);
      setIntro(false);
      return;
    }
    const v = videoRef.current;
    if (!v) {
      next();
      return;
    }
    // Тот же файл заново не качаем — перематываем в начало.
    if (v.getAttribute("src") !== step.src) v.src = step.src;
    else v.currentTime = 0;
    // Автозапуск запрещён или файла нет — не зависаем, а идём дальше.
    v.play().catch(() => next());
  }

  function run(steps: Step[], isIntro = false) {
    chain.current = { steps: [...steps] };
    setBusy(true);
    if (isIntro) setIntro(true);
    next();
  }

  function skip() {
    videoRef.current?.pause();
    next();
  }

  // Первый кадр на экране: фоном готовим следующий шаг и показываем
  // вступление (раз за визит; без анимаций по системной настройке — нет).
  function onHeroReady() {
    if (started.current) return;
    started.current = true;
    window.setTimeout(() => need("floor:3:eve", "hotel:day"), 1500);
    if (!withIntro || prefersReducedMotion()) return;
    let seen = false;
    try {
      seen = sessionStorage.getItem("airis3d-intro") === "1";
      sessionStorage.setItem("airis3d-intro", "1");
    } catch {
      /* без хранилища просто покажем вступление */
    }
    // Через тик: кадр может оказаться готов раньше, чем подключён <video>.
    if (!seen)
      window.setTimeout(() => run([{ src: "/3d/intro.mp4" }], true), 30);
  }

  // ── Навигация ─────────────────────────────────────────────────────────
  function warmBelow(v: View) {
    const i = ORDER.indexOf(v);
    const below = ORDER[i + 1];
    if (below !== undefined)
      window.setTimeout(() => need(keyOf(below, null, tod)), 600);
  }

  function navigate(from: View, target: View) {
    if (target === from) return;
    if (target === "lobby") {
      enterLobby(from);
      return;
    }
    if (from === "lobby") {
      // Со стойки — наплывом; к зданию ещё и с отъездом от дверей.
      const k = keyOf(target, null, tod);
      ready(k).then(() => {
        need(k);
        if (target === "hotel")
          setBack((b) => ({ p: ENTRANCE, n: (b?.n ?? 0) + 1 }));
        setView(target);
      });
      return;
    }
    const a = ORDER.indexOf(from);
    const b = ORDER.indexOf(target);
    if (b < a) {
      // Вверх — без ролика, наплывом.
      const k = keyOf(target, null, tod);
      ready(k).then(() => {
        need(k);
        setView(target);
      });
      return;
    }
    // Вниз — ролики подряд; кадры этажей грузятся, пока они играют.
    const steps: Step[] = [];
    for (let i = a; i < b; i += 1) {
      const to = ORDER[i + 1];
      need(keyOf(to, null, tod));
      steps.push({
        src: TRANSITIONS[tod][`${ORDER[i]}>${to}`],
        then: () => setView(to),
      });
    }
    steps[steps.length - 1].then = () => {
      setView(target);
      warmBelow(target);
    };
    run(steps);
  }

  function go(target: View) {
    if (busy) return;
    setHover(null);
    setPhotos(false);
    if (room) {
      leaveRoom();
      if (target !== view) navigate(view, target);
      return;
    }
    navigate(view, target);
  }

  /** Войти в отель: наезд на двери → проход к стойке → приветствие. */
  function enterLobby(from: View) {
    const k = keyOf("lobby", null, tod);
    const walk = `/3d/lobby-in-${tod}.mp4`;
    const greet = { src: `/3d/greet-${tod}.mp4` };
    need(k);
    setHover(null);
    setFocusCat(null);
    if (from !== "hotel") {
      // С этажа идти через улицу странно — сразу к стойке и приветствие.
      ready(k).then(() => {
        setView("lobby");
        run([greet]);
      });
      return;
    }
    setBusy(true);
    setZoom(ENTRANCE);
    const v = videoRef.current;
    if (v && v.getAttribute("src") !== walk) {
      v.src = walk;
      v.load();
    }
    window.setTimeout(
      () =>
        run([
          {
            src: walk,
            then: () => {
              setView("lobby");
              setZoom(null);
            },
          },
          greet,
        ]),
      prefersReducedMotion() ? 0 : ZOOM_MS - 100,
    );
  }

  function enterRoom(p: Point) {
    if (busy) return;
    const src = `/3d/rooms/${slug(p.cat)}-${tod}.mp4`;
    need(keyOf(view, p, tod));
    setHover(null);
    setFocusCat(null);
    setBusy(true);
    setZoom(p);
    // Ролик начинает качаться сразу, а играть — когда камера «долетела».
    const v = videoRef.current;
    if (v && v.getAttribute("src") !== src) {
      v.src = src;
      v.load();
    }
    window.setTimeout(
      () =>
        run([
          {
            src,
            then: () => {
              setRoom(p);
              setZoom(null);
            },
          },
        ]),
      prefersReducedMotion() ? 0 : ZOOM_MS - 100,
    );
  }

  function leaveRoom() {
    if (!room) return;
    const p = room;
    // n меняет имя анимации, если выйти снова, не дождавшись конца прошлой.
    setBack((b) => ({ p, n: (b?.n ?? 0) + 1 }));
    setRoom(null);
    setPhotos(false);
  }

  function pickTod(t: Tod) {
    if (busy || t === tod) return;
    const k = keyOf(view, room, t);
    ready(k).then(() => {
      need(k);
      setTod(t);
    });
  }

  // ── Данные этажа ──────────────────────────────────────────────────────
  const floorPoints = useMemo<Point[]>(
    () =>
      view === "hotel" || view === "lobby"
        ? []
        : ((points as Record<string, Point[]>)[String(view)] ?? []),
    [view],
  );
  const counts = useMemo(() => {
    const c: Partial<Record<Cat, number>> = {};
    for (const p of floorPoints) c[p.cat] = (c[p.cat] ?? 0) + 1;
    return c;
  }, [floorPoints]);

  const info = room ? cats[room.cat] : null;
  const showSpots =
    !busy && !room && !zoom && view !== "hotel" && view !== "lobby";

  return (
    <div>
      <div className="relative">
        <div className="overflow-hidden rounded-card border border-white/8 bg-ink-900 shadow-deep">
          <div className="relative aspect-[1920/1086] select-none">
            {mounted.map((k) => {
              const active = k === current;
              const isFloor = k.startsWith("floor:") || k.startsWith("hotel:");
              const zin = isFloor && active ? zoom : null;
              const zout = isFloor && active && !zoom ? back : null;
              const b = basePath(k);
              return (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={k}
                  src={`${b}.webp`}
                  srcSet={`${b}-960.webp 960w, ${b}.webp 1920w`}
                  sizes={IMG_SIZES}
                  alt={active ? altOf(k) : ""}
                  aria-hidden={!active}
                  decoding="async"
                  fetchPriority={k === "hotel:eve" ? "high" : "low"}
                  draggable={false}
                  ref={
                    k === "hotel:eve"
                      ? (el) => {
                          if (el?.complete && el.naturalWidth) onHeroReady();
                        }
                      : undefined
                  }
                  onLoad={k === "hotel:eve" ? onHeroReady : undefined}
                  onAnimationEnd={zout ? () => setBack(null) : undefined}
                  className="absolute inset-0 h-full w-full object-fill"
                  style={{
                    zIndex: active ? 2 : 1,
                    opacity: active ? 1 : 0,
                    // Новый кадр проявляется сверху, старый уходит, когда
                    // новый уже на месте, — без провала в тёмный фон.
                    transition: active
                      ? `opacity 600ms ease, transform ${ZOOM_MS}ms cubic-bezier(.55,0,.45,1)`
                      : `opacity 250ms ease 600ms, transform ${ZOOM_MS}ms cubic-bezier(.55,0,.45,1)`,
                    transform: zin ? `scale(${ZOOM})` : undefined,
                    transformOrigin: zin
                      ? `${zin.x}% ${zin.y}%`
                      : zout
                        ? `${zout.p.x}% ${zout.p.y}%`
                        : undefined,
                    animation: zout
                      ? `h3d-out-${zout.n % 2 ? "a" : "b"} 900ms cubic-bezier(.2,.7,.2,1) both`
                      : undefined,
                  }}
                />
              );
            })}

            <video
              ref={videoRef}
              muted
              playsInline
              preload="auto"
              onPlaying={() => setVideoOn(true)}
              onEnded={next}
              onError={next}
              className="absolute inset-0 z-[5] h-full w-full object-fill"
              style={{
                opacity: videoOn ? 1 : 0,
                // Гасим ролик, когда под ним уже проявился конечный кадр.
                transition: videoOn
                  ? "opacity 200ms ease"
                  : "opacity 300ms ease 550ms",
                pointerEvents: "none",
              }}
            />

            {/* Ролик ещё качается — кружок появится, только если ждать дольше секунды */}
            {busy && !videoOn && (
              <span className="h3d-wait pointer-events-none absolute inset-0 z-[6] grid place-items-center">
                <span className="h-8 w-8 animate-spin rounded-full border-2 border-white/25 border-t-sand-300" />
              </span>
            )}

            {intro && (
              <button
                type="button"
                onClick={skip}
                className="absolute bottom-3 left-3 z-20 rounded-full border border-white/20 bg-ink-950/75 px-4 py-2 text-xs text-cream md:bottom-4 md:left-4"
              >
                Пропустить
              </button>
            )}

            {/* Номера на этаже. Центр кружка — точка: контейнер нулевого
                размера с центровкой flex, без transform (его глушит
                «уменьшить движение»). */}
            {showSpots &&
              floorPoints.map((p, i) => {
                const dim = focusCat && focusCat !== p.cat;
                const c = cats[p.cat];
                return (
                  <button
                    key={p.id}
                    type="button"
                    aria-label={`Зайти в номер: ${c.name}${c.priceText ? `, ${c.priceText}` : ""}`}
                    onClick={() => enterRoom(p)}
                    onMouseEnter={() => setHover(p.id)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(p.id)}
                    onBlur={() => setHover(null)}
                    style={{
                      left: `${p.x}%`,
                      top: `${p.y}%`,
                      ["--c" as string]: CAT_COLOR[p.cat],
                    }}
                    className={`group absolute z-10 flex h-0 w-0 items-center justify-center transition-opacity duration-300 ${
                      dim ? "opacity-25" : "opacity-100"
                    }`}
                  >
                    <span
                      className="h3d-pop flex h-7 w-7 shrink-0 items-center justify-center rounded-full md:h-9 md:w-9"
                      style={{ animationDelay: `${i * 35}ms` }}
                    >
                      <span className="block h-3.5 w-3.5 rounded-full border-2 border-white bg-[var(--c)] shadow-[0_0_0_4px_color-mix(in_srgb,var(--c)_35%,transparent),0_2px_8px_rgba(0,0,0,.5)] transition-[width,height] duration-200 group-hover:h-5 group-hover:w-5 group-focus-visible:h-5 group-focus-visible:w-5 md:h-5 md:w-5 md:group-hover:h-6 md:group-hover:w-6" />
                    </span>
                    {hover === p.id && (
                      <span className="pointer-events-none absolute bottom-3 flex w-0 justify-center md:bottom-4">
                        <span className="rounded-xl border border-white/15 bg-ink-950/92 px-3 py-2 text-left text-xs whitespace-nowrap text-cream shadow-lift">
                          <span className="block font-semibold">{c.name}</span>
                          {c.priceText && (
                            <span className="block text-sand-200">
                              {c.priceText}
                            </span>
                          )}
                          <span className="mt-0.5 block text-[0.68rem] text-muted">
                            Нажмите — зайдём внутрь
                          </span>
                        </span>
                      </span>
                    )}
                  </button>
                );
              })}

            {/* Вечер / день — на любом шаге */}
            {!intro && (
              <div className="absolute top-2 left-2 z-20 flex rounded-full border border-white/15 bg-ink-950/75 p-0.5 text-[0.65rem] md:top-4 md:left-4 md:p-1 md:text-xs">
                {(
                  [
                    { t: "eve", label: "Вечер" },
                    { t: "day", label: "День" },
                  ] as const
                ).map((o) => (
                  <button
                    key={o.t}
                    type="button"
                    disabled={busy}
                    aria-pressed={tod === o.t}
                    onClick={() => pickTod(o.t)}
                    className={`rounded-full px-2.5 py-1 transition-colors md:px-3.5 md:py-1.5 ${
                      tod === o.t
                        ? "bg-sand-300 text-ink-950"
                        : "text-cream/80 hover:text-cream"
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            )}

            {room && !busy && (
              <button
                type="button"
                onClick={leaveRoom}
                className="absolute top-2 right-2 z-20 rounded-full border border-white/15 bg-ink-950/75 px-3 py-1.5 text-[0.7rem] text-cream transition-colors hover:border-sand-300/60 md:top-4 md:right-4 md:px-4 md:py-2 md:text-xs"
              >
                ← К этажу
              </button>
            )}

            {view === "hotel" && !busy && !room && (
              <div className="absolute inset-x-0 bottom-3 z-20 flex justify-center gap-2 md:bottom-5 md:gap-3">
                <button
                  type="button"
                  onClick={() => go("lobby")}
                  className="rounded-full bg-sand-300 px-4 py-2 text-xs font-medium text-ink-950 shadow-lift transition-colors hover:bg-sand-200 md:px-6 md:py-3 md:text-sm"
                >
                  Войти в отель
                </button>
                <button
                  type="button"
                  onClick={() => go(3)}
                  className="rounded-full border border-white/25 bg-ink-950/75 px-4 py-2 text-xs font-medium text-cream shadow-lift transition-colors hover:border-sand-300/70 md:px-6 md:py-3 md:text-sm"
                >
                  Снять крышу
                </button>
              </div>
            )}

            {showSpots && (
              <p className="pointer-events-none absolute inset-x-0 bottom-2 z-20 hidden justify-center md:flex">
                <span className="rounded-full bg-ink-950/75 px-4 py-1.5 text-xs text-cream/85">
                  Нажмите на кружок — зайдём в номер
                </span>
              </p>
            )}

            {/* Карточка номера поверх кадра — на широком экране */}
            {room && info && !busy && (
              <div className="absolute bottom-4 left-4 z-20 hidden w-[23rem] md:block">
                <RoomCard
                  info={info}
                  color={CAT_COLOR[room.cat]}
                  floor={view}
                  onPhotos={() => setPhotos(true)}
                />
              </div>
            )}
          </div>
        </div>

        {/* Этажи */}
        <nav
          aria-label="Этажи отеля"
          className="mt-3 flex justify-center gap-2 md:pointer-events-none md:absolute md:inset-y-0 md:right-4 md:z-20 md:mt-0 md:flex-col md:justify-center"
        >
          {NAV.map((v) => (
            <button
              key={String(v)}
              type="button"
              disabled={busy}
              aria-current={view === v && !room ? "true" : undefined}
              onClick={() => go(v)}
              className={`rounded-full border px-2.5 py-2 text-xs transition-colors disabled:opacity-60 sm:px-3 md:pointer-events-auto md:min-w-[5.5rem] md:px-4 ${
                view === v
                  ? "border-sand-300 bg-sand-300 text-ink-950"
                  : "border-white/15 bg-ink-950/80 text-cream/85 hover:border-sand-300/60 hover:text-cream"
              }`}
            >
              {typeof v === "number" ? (
                <>
                  {v}
                  <span className="hidden sm:inline"> этаж</span>
                  <span className="sm:hidden"> эт.</span>
                </>
              ) : (
                VIEW_LABEL[String(v)]
              )}
            </button>
          ))}
        </nav>

        {/* Чат со стойкой: на широком экране поверх кадра справа от
            администратора, на узком — под кадром. Один экземпляр, чтобы
            переписка не раздваивалась. */}
        {view === "lobby" && !room && (
          <ReceptionChat className="mt-4 h-[30rem] lg:absolute lg:top-4 lg:right-[7.5rem] lg:bottom-4 lg:z-20 lg:mt-0 lg:h-auto lg:w-[23rem]" />
        )}
      </div>

      {/* Карточка номера под кадром — на телефоне */}
      {room && info && !busy && (
        <div className="mt-4 md:hidden">
          <RoomCard
            info={info}
            color={CAT_COLOR[room.cat]}
            floor={view}
            onPhotos={() => setPhotos(true)}
          />
        </div>
      )}

      {/* Легенда */}
      {!room && view !== "lobby" && (
        <div className="mt-5 flex flex-wrap gap-2">
          {CAT_ORDER.filter((k) => view === "hotel" || counts[k]).map((k) => (
            <button
              key={k}
              type="button"
              onMouseEnter={() => setFocusCat(k)}
              onMouseLeave={() => setFocusCat(null)}
              onClick={() => setFocusCat((f) => (f === k ? null : k))}
              className={`flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs transition-colors ${
                focusCat === k
                  ? "border-white/40 bg-white/10"
                  : "border-white/10 bg-ink-800 hover:border-white/25"
              }`}
            >
              <span
                className="h-3 w-3 rounded-full"
                style={{ background: CAT_COLOR[k] }}
              />
              <span className="text-cream">{cats[k].name}</span>
              {cats[k].priceText && (
                <span className="text-muted">{cats[k].priceText}</span>
              )}
              {view !== "hotel" && counts[k] ? (
                <span className="text-muted">· {counts[k]}</span>
              ) : null}
            </button>
          ))}
        </div>
      )}

      {/* Фото номера — шторка */}
      {photos && info && room && (
        <div
          className="fixed inset-0 z-[60] flex justify-end bg-ink-950/75"
          onClick={() => setPhotos(false)}
        >
          <aside
            role="dialog"
            aria-label={`Фото: ${info.name}`}
            onClick={(e) => e.stopPropagation()}
            className="mt-auto max-h-[88vh] w-full overflow-y-auto rounded-t-card border border-white/10 bg-ink-900 md:mt-0 md:h-full md:max-h-none md:max-w-md md:rounded-none md:border-y-0 md:border-r-0"
          >
            <RoomPanel
              info={info}
              color={CAT_COLOR[room.cat]}
              floor={view}
              onClose={() => setPhotos(false)}
            />
          </aside>
        </div>
      )}
    </div>
  );
}

function RoomCard({
  info,
  color,
  floor,
  onPhotos,
}: {
  info: CatInfo;
  color: string;
  floor: View;
  onPhotos: () => void;
}) {
  return (
    <div className="rounded-2xl border border-white/12 bg-ink-950/88 p-4 text-cream shadow-lift md:p-5">
      <p className="flex items-center gap-2 text-[0.68rem] tracking-[0.14em] text-muted uppercase">
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ background: color }}
        />
        {floor === "hotel" ? "Номер" : `${floor} этаж`}
      </p>
      <div className="mt-1.5 flex items-baseline justify-between gap-3">
        <h3 className="font-display text-xl md:text-2xl">{info.name}</h3>
        {info.priceText && (
          <p className="shrink-0 font-display text-lg text-sand-200">
            {info.priceText}
          </p>
        )}
      </div>
      <p className="mt-1 text-xs text-muted">
        {[
          info.area,
          `до ${info.capacity} ${info.capacity === 1 ? "гостя" : "гостей"}`,
          info.beds,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <a
          href={info.bookHref}
          className="rounded-full bg-sand-300 px-4 py-2.5 text-sm font-medium text-ink-950 transition-colors hover:bg-sand-200"
        >
          Забронировать
        </a>
        <button
          type="button"
          onClick={onPhotos}
          className="rounded-full border border-white/15 px-4 py-2.5 text-sm text-cream/85 hover:border-sand-300/50"
        >
          {info.images.length ? "Фото номера" : "Видеообзор"}
        </button>
        {info.href && (
          <Link
            href={info.href}
            className="rounded-full border border-white/15 px-4 py-2.5 text-sm text-cream/85 hover:border-sand-300/50"
          >
            Подробнее
          </Link>
        )}
      </div>
      <p className="mt-3 text-[0.68rem] leading-relaxed text-muted">
        Интерьер — визуализация по фото этой категории. Номер комнаты назначает
        стойка при заселении.
      </p>
    </div>
  );
}

function RoomPanel({
  info,
  color,
  floor,
  onClose,
}: {
  info: CatInfo;
  color: string;
  floor: View;
  onClose: () => void;
}) {
  const [i, setI] = useState(0);
  return (
    <div className="flex min-h-full flex-col">
      <div className="relative aspect-4/3 w-full bg-ink-800">
        {info.images.length > 0 ? (
          <Image
            src={info.images[i]}
            alt={info.name}
            fill
            sizes="(max-width: 768px) 100vw, 448px"
            className="object-cover"
          />
        ) : info.video ? (
          <video
            src={info.video}
            controls
            muted
            playsInline
            preload="metadata"
            className="h-full w-full object-cover"
          />
        ) : null}
        <button
          type="button"
          onClick={onClose}
          aria-label="Закрыть"
          className="absolute top-3 right-3 flex h-9 w-9 items-center justify-center rounded-full bg-ink-950/80 text-lg text-cream"
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
              <Image
                src={src}
                alt=""
                fill
                sizes="80px"
                className="object-cover"
              />
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-1 flex-col p-5 md:p-6">
        <p className="flex items-center gap-2 text-[0.7rem] tracking-[0.14em] text-muted uppercase">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ background: color }}
          />
          {floor === "hotel" ? "" : `${floor} этаж`}
        </p>
        <h3 className="mt-2 font-display text-2xl text-cream">{info.name}</h3>
        <p className="mt-2 text-sm text-muted">
          {[
            info.area,
            `до ${info.capacity} ${info.capacity === 1 ? "гостя" : "гостей"}`,
            info.beds,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {info.summary && (
          <p className="mt-4 text-sm leading-relaxed text-cream/85">
            {info.summary}
          </p>
        )}
        <div className="mt-auto pt-6">
          {info.priceText && (
            <p className="font-display text-2xl text-sand-200">
              {info.priceText}
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href={info.bookHref}
              className="rounded-full bg-sand-300 px-5 py-3 text-sm font-medium text-ink-950 transition-colors hover:bg-sand-200"
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
            Фото — реальные фото номеров этой категории. Номер комнаты назначает
            стойка при заселении.
          </p>
        </div>
      </div>
    </div>
  );
}
