"use client";

import { motion, type Variants } from "motion/react";
import type { ReactNode } from "react";

import { usePrefersReducedMotion } from "@/lib/useMediaQuery";

type Direction = "up" | "left" | "right" | "none";

const offset: Record<Direction, { x: number; y: number }> = {
  up: { x: 0, y: 28 },
  left: { x: -28, y: 0 },
  right: { x: 28, y: 0 },
  none: { x: 0, y: 0 },
};

/**
 * Появление блока при входе в вьюпорт. Внутри — небольшой поворот
 * по оси X, из-за чего блок «встаёт» из глубины: это и даёт
 * ощущение объёма при прокрутке.
 */
export function Reveal({
  children,
  delay = 0,
  direction = "up",
  depth = true,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  direction?: Direction;
  depth?: boolean;
  className?: string;
}) {
  const reduced = usePrefersReducedMotion();
  const { x, y } = offset[direction];

  if (reduced) return <div className={className}>{children}</div>;

  const variants: Variants = {
    hidden: {
      opacity: 0,
      x,
      y,
      rotateX: depth ? 8 : 0,
      scale: depth ? 0.97 : 1,
    },
    visible: {
      opacity: 1,
      x: 0,
      y: 0,
      rotateX: 0,
      scale: 1,
      transition: { duration: 0.85, delay, ease: [0.16, 1, 0.3, 1] },
    },
  };

  return (
    <motion.div
      className={className}
      style={depth ? { transformPerspective: 1200 } : undefined}
      variants={variants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-80px" }}
    >
      {children}
    </motion.div>
  );
}

/** Построчное появление заголовка — слова «набегают» друг за другом. */
export function RevealWords({
  text,
  className = "",
  wordClassName = "",
  delay = 0,
}: {
  text: string;
  className?: string;
  wordClassName?: string;
  delay?: number;
}) {
  const reduced = usePrefersReducedMotion();
  const words = text.split(" ");

  if (reduced) return <span className={className}>{text}</span>;

  return (
    <motion.span
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-60px" }}
      transition={{ staggerChildren: 0.06, delayChildren: delay }}
    >
      {words.map((word, i) => (
        <span key={`${word}-${i}`} className="inline-block overflow-hidden align-bottom">
          <motion.span
            className={`inline-block ${wordClassName}`}
            variants={{
              hidden: { y: "110%", opacity: 0 },
              visible: {
                y: "0%",
                opacity: 1,
                transition: { duration: 0.75, ease: [0.16, 1, 0.3, 1] },
              },
            }}
          >
            {word}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </motion.span>
  );
}
