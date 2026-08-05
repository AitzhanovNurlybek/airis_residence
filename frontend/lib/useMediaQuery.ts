"use client";

import { useEffect, useState } from "react";

/**
 * Медиазапрос как реактивное значение.
 *
 * До гидрации возвращает false — так тяжёлые десктопные эффекты
 * (WebGL, скролл-анимации) не успевают запуститься на телефоне,
 * даже на миг.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(query);
    setMatches(mql.matches);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/** Десктоп: широкий экран И указатель мыши (планшет в ландшафте не считается). */
export const useIsDesktop = () =>
  useMediaQuery("(min-width: 1024px) and (pointer: fine)");

/** Телефон и всё, что уже узкого брейкпоинта md. */
export const useIsMobile = () => useMediaQuery("(max-width: 767px)");

/**
 * «Уменьшить анимацию» в настройках системы.
 *
 * Намеренно НЕ используем useReducedMotion из motion: тот читает настройку
 * прямо во время рендера, из-за чего сервер и браузер строят разные деревья
 * и React ругается на несовпадение гидратации. Здесь первый рендер всегда
 * одинаковый (false), а настройка применяется сразу после монтирования.
 */
export const usePrefersReducedMotion = () =>
  useMediaQuery("(prefers-reduced-motion: reduce)");
