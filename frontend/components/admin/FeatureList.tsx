"use client";

import { useState } from "react";
import { inputClass } from "@/components/admin/ui";

/** Редактор списка «Оснащение номера»: добавить, изменить, переставить, убрать. */
export function FeatureList({
  items,
  onChange,
  className = "",
}: {
  items: string[];
  onChange: (items: string[]) => void;
  className?: string;
}) {
  const [draft, setDraft] = useState("");

  const add = () => {
    const value = draft.trim();
    if (!value) return;
    onChange([...items, value]);
    setDraft("");
  };

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  return (
    <div className={className}>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={index} className="flex items-center gap-2">
            <input
              className={inputClass}
              value={item}
              onChange={(e) =>
                onChange(items.map((v, i) => (i === index ? e.target.value : v)))
              }
            />
            <div className="flex shrink-0 gap-1">
              <button
                type="button"
                aria-label="Выше"
                disabled={index === 0}
                onClick={() => move(index, -1)}
                className="grid size-9 place-items-center rounded-lg border border-white/12 text-muted transition-colors hover:text-cream disabled:opacity-30"
              >
                ↑
              </button>
              <button
                type="button"
                aria-label="Ниже"
                disabled={index === items.length - 1}
                onClick={() => move(index, 1)}
                className="grid size-9 place-items-center rounded-lg border border-white/12 text-muted transition-colors hover:text-cream disabled:opacity-30"
              >
                ↓
              </button>
              <button
                type="button"
                aria-label="Убрать пункт"
                onClick={() => onChange(items.filter((_, i) => i !== index))}
                className="grid size-9 place-items-center rounded-lg border border-white/12 text-muted transition-colors hover:border-wine-400/50 hover:text-wine-200"
              >
                ✕
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-3 flex gap-2">
        <input
          className={inputClass}
          placeholder="Добавить пункт: сейф, мини-бар, халаты…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <button
          type="button"
          onClick={add}
          disabled={!draft.trim()}
          className="shrink-0 rounded-xl border border-white/15 px-5 text-sm text-cream transition-colors hover:border-sand-400/50 disabled:opacity-40"
        >
          Добавить
        </button>
      </div>
    </div>
  );
}
