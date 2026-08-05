import { Manrope, Playfair_Display } from "next/font/google";

/**
 * Шрифты вынесены отдельно: у сайта и у админки разные корневые
 * лейауты, а шрифты нужны обоим. next/font при этом всё равно
 * подгрузит каждый файл один раз.
 *
 * Кириллица подключена явно — без неё казахские ә, ғ, қ, ң, ө, ұ, ү, һ, і
 * подставлялись бы запасным системным шрифтом.
 */

export const display = Playfair_Display({
  subsets: ["latin", "cyrillic"],
  variable: "--font-display",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const sans = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-sans",
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

export const fontClass = `${display.variable} ${sans.variable}`;
