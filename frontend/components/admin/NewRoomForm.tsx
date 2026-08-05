"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { adminSend, AdminError } from "@/lib/adminClient";
import type { AdminRoom } from "@/lib/adminTypes";
import { AdminButton, Field, inputClass, useToast } from "@/components/admin/ui";

/** Транслитерация названия в адрес страницы: «Полулюкс» → «polulyuks». */
const MAP: Record<string, string> = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z",
  и: "i", й: "y", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r",
  с: "s", т: "t", у: "u", ф: "f", х: "h", ц: "c", ч: "ch", ш: "sh",
  щ: "sch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .split("")
    .map((ch) => MAP[ch] ?? ch)
    .join("")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 58);
}

export function NewRoomForm() {
  const router = useRouter();
  const toast = useToast();

  const [shortName, setShortName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [price, setPrice] = useState(45000);
  const [area, setArea] = useState("");
  const [capacity, setCapacity] = useState(2);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;

    const finalSlug = slug || slugify(shortName);
    if (!shortName.trim() || !finalSlug) {
      toast.show("Укажите название номера", "error");
      return;
    }

    setBusy(true);
    try {
      const room = await adminSend<AdminRoom>("/rooms", "POST", {
        slug: finalSlug,
        name: `Номер «${shortName.trim()}»`,
        shortName: shortName.trim(),
        price,
        area,
        capacity,
        beds: "",
        summary: "",
        description: "",
        features: [],
      });
      toast.show("Номер создан. Добавьте фотографии и описание.");
      router.push(`/admin/nomera/${room.slug}`);
      router.refresh();
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось создать номер", "error");
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <Link href="/admin" className="text-sm text-muted transition-colors hover:text-cream">
        ← Все номера
      </Link>

      <h1 className="mt-4 font-display text-3xl text-cream md:text-4xl">Новый номер</h1>
      <p className="mt-2 text-sm text-muted">
        Заполните основное — фотографии и описание добавите на следующем шаге.
        Новый номер появляется на сайте только после того, как вы его опубликуете.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5">
        <Field label="Название" hint="Так номер будет называться в списке: Standart, Luxe, Полулюкс">
          <input
            className={inputClass}
            value={shortName}
            autoFocus
            onChange={(e) => {
              setShortName(e.target.value);
              if (!slugTouched) setSlug(slugify(e.target.value));
            }}
          />
        </Field>

        <Field
          label="Адрес страницы"
          hint={`Страница будет доступна по адресу /nomera/${slug || "…"}. Потом изменить нельзя.`}
        >
          <input
            className={inputClass}
            value={slug}
            onChange={(e) => {
              setSlugTouched(true);
              setSlug(slugify(e.target.value));
            }}
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-3">
          <Field label="Цена за ночь, ₸">
            <input
              type="number"
              min={0}
              step={500}
              className={`${inputClass} tabular-nums`}
              value={price}
              onChange={(e) => setPrice(Number(e.target.value))}
            />
          </Field>
          <Field label="Площадь">
            <input
              className={inputClass}
              placeholder="25 м²"
              value={area}
              onChange={(e) => setArea(e.target.value)}
            />
          </Field>
          <Field label="Максимум гостей">
            <input
              type="number"
              min={1}
              max={10}
              className={inputClass}
              value={capacity}
              onChange={(e) => setCapacity(Number(e.target.value))}
            />
          </Field>
        </div>

        <AdminButton type="submit" disabled={busy}>
          {busy ? "Создаём…" : "Создать номер"}
        </AdminButton>
      </form>
    </div>
  );
}
