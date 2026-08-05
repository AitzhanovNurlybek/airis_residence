"use client";

import { useEffect } from "react";
import Lenis from "lenis";

/**
 * Инерционный скролл. Даёт «тяжёлое» ощущение прокрутки, на котором
 * держится вся параллакс-механика сайта.
 * Отключается для пользователей с prefers-reduced-motion.
 */
export function SmoothScroll() {
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const lenis = new Lenis({
      duration: 1.15,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      // На тач-устройствах нативный скролл ощущается лучше и не ломает fixed-элементы.
      syncTouch: false,
    });

    let frame = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);

    // Якорные ссылки (#nomera и т.п.) должны ехать через Lenis.
    const onClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest?.('a[href*="#"]');
      if (!anchor) return;
      const href = anchor.getAttribute("href") ?? "";
      const hash = href.includes("#") ? `#${href.split("#")[1]}` : "";
      if (!hash || hash === "#") return;
      const samePage = href.startsWith("#") || href.startsWith("/#");
      if (!samePage) return;
      const target = document.querySelector(hash);
      if (!target) return;
      e.preventDefault();
      lenis.scrollTo(target as HTMLElement, { offset: -80 });
      history.replaceState(null, "", hash);
    };

    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("click", onClick);
      cancelAnimationFrame(frame);
      lenis.destroy();
    };
  }, []);

  return null;
}
