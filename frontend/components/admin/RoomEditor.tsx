"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { adminSend, AdminError } from "@/lib/adminClient";
import type { AdminRoom } from "@/lib/adminTypes";
import { formatPrice } from "@/lib/site";
import { AdminButton, Field, SaveBar, inputClass, useToast } from "@/components/admin/ui";
import { PhotoManager } from "@/components/admin/PhotoManager";
import { VideoManager } from "@/components/admin/VideoManager";
import { FeatureList } from "@/components/admin/FeatureList";

export function RoomEditor({ room: initial }: { room: AdminRoom }) {
  const [room, setRoom] = useState(initial);
  const [saved, setSaved] = useState(initial);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const router = useRouter();

  // Фотографии и видео сохраняются отдельно и мгновенно, поэтому в
  // сравнение «есть ли несохранённые правки» они не входят.
  const dirty = useMemo(() => {
    const strip = ({ images, video, ...rest }: AdminRoom) => rest;
    return JSON.stringify(strip(room)) !== JSON.stringify(strip(saved));
  }, [room, saved]);

  const set = <K extends keyof AdminRoom>(key: K, value: AdminRoom[K]) =>
    setRoom((prev) => ({ ...prev, [key]: value }));

  const save = async () => {
    setSaving(true);
    try {
      const updated = await adminSend<AdminRoom>(`/rooms/${room.slug}`, "PATCH", {
        name: room.name,
        shortName: room.shortName,
        price: room.price,
        area: room.area,
        capacity: room.capacity,
        beds: room.beds,
        summary: room.summary,
        description: room.description,
        features: room.features,
        isPublished: room.isPublished,
      });
      setRoom(updated);
      setSaved(updated);
      toast.show("Изменения сохранены и уже на сайте");
      router.refresh();
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось сохранить", "error");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Удалить номер «${room.shortName}» вместе с фотографиями?`)) return;
    try {
      await adminSend(`/rooms/${room.slug}`, "DELETE");
      toast.show("Номер удалён");
      router.push("/admin");
      router.refresh();
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось удалить", "error");
    }
  };

  return (
    <div>
      <Link href="/admin" className="text-sm text-muted transition-colors hover:text-cream">
        ← Все номера
      </Link>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-cream md:text-4xl">{room.shortName}</h1>
          <p className="mt-2 text-sm text-muted">
            Адрес на сайте:{" "}
            <Link
              href={`/nomera/${room.slug}`}
              target="_blank"
              className="text-sand-300 underline underline-offset-4"
            >
              /nomera/{room.slug} ↗
            </Link>
          </p>
        </div>

        <button
          type="button"
          onClick={() => set("isPublished", !room.isPublished)}
          className={`rounded-full border px-4 py-2.5 text-sm transition-colors ${
            room.isPublished
              ? "border-emerald-400/40 text-emerald-200"
              : "border-white/20 text-muted"
          }`}
        >
          {room.isPublished ? "Виден на сайте" : "Скрыт с сайта"}
        </button>
      </div>

      <div className="mt-10 space-y-12">
        {/* ---------- Цена и параметры ---------- */}
        <section>
          <h2 className="font-display text-xl text-cream">Цена и параметры</h2>
          <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Цена за ночь, ₸" hint={formatPrice(room.price)}>
              <input
                type="number"
                min={0}
                step={500}
                className={`${inputClass} tabular-nums`}
                value={room.price}
                onChange={(e) => set("price", Number(e.target.value))}
              />
            </Field>
            <Field label="Площадь" hint="Например: 18–20 м²">
              <input
                className={inputClass}
                value={room.area}
                onChange={(e) => set("area", e.target.value)}
              />
            </Field>
            <Field label="Максимум гостей">
              <input
                type="number"
                min={1}
                max={10}
                className={inputClass}
                value={room.capacity}
                onChange={(e) => set("capacity", Number(e.target.value))}
              />
            </Field>
            <Field label="Спальные места" hint="Например: двуспальная кровать 180×200">
              <input
                className={inputClass}
                value={room.beds}
                onChange={(e) => set("beds", e.target.value)}
              />
            </Field>
          </div>
        </section>

        {/* ---------- Тексты ---------- */}
        <section>
          <h2 className="font-display text-xl text-cream">Названия и тексты</h2>
          <div className="mt-5 space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Короткое название" hint="Видно в списке номеров и в меню">
                <input
                  className={inputClass}
                  value={room.shortName}
                  onChange={(e) => set("shortName", e.target.value)}
                />
              </Field>
              <Field label="Полное название" hint="Заголовок страницы номера">
                <input
                  className={inputClass}
                  value={room.name}
                  onChange={(e) => set("name", e.target.value)}
                />
              </Field>
            </div>

            <Field
              label="Краткое описание"
              hint="Одно-два предложения на карточке в списке номеров"
            >
              <textarea
                rows={2}
                className={`${inputClass} resize-y`}
                value={room.summary}
                onChange={(e) => set("summary", e.target.value)}
              />
            </Field>

            <Field label="Полное описание" hint="Текст на странице номера">
              <textarea
                rows={5}
                className={`${inputClass} resize-y`}
                value={room.description}
                onChange={(e) => set("description", e.target.value)}
              />
            </Field>
          </div>
        </section>

        {/* ---------- Оснащение ---------- */}
        <section>
          <h2 className="font-display text-xl text-cream">Оснащение</h2>
          <p className="mt-1 text-sm text-muted">
            Список пунктов на странице номера. Порядок такой же, как здесь.
          </p>
          <FeatureList
            items={room.features}
            onChange={(features) => set("features", features)}
            className="mt-5"
          />
        </section>

        {/* ---------- Фотографии ---------- */}
        <PhotoManager
          slug={room.slug}
          images={room.images}
          onChange={(images) => {
            setRoom((prev) => ({ ...prev, images }));
            setSaved((prev) => ({ ...prev, images }));
            router.refresh();
          }}
        />

        {/* ---------- Видеообзор ---------- */}
        <VideoManager
          slug={room.slug}
          video={room.video}
          poster={room.images[0]}
          onChange={(video) => {
            setRoom((prev) => ({ ...prev, video }));
            setSaved((prev) => ({ ...prev, video }));
            router.refresh();
          }}
        />

        {/* ---------- Опасная зона ---------- */}
        <section className="rounded-2xl border border-wine-400/25 p-6">
          <h2 className="font-display text-lg text-cream">Удалить номер</h2>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Номер и его фотографии удалятся навсегда, страница{" "}
            <span className="text-cream/80">/nomera/{room.slug}</span> перестанет
            открываться. Если номер просто временно не сдаётся — лучше скрыть его,
            а не удалять.
          </p>
          <AdminButton variant="danger" className="mt-5" onClick={remove}>
            Удалить номер
          </AdminButton>
        </section>
      </div>

      <SaveBar
        dirty={dirty}
        saving={saving}
        onSave={save}
        onReset={() => setRoom(saved)}
      />
    </div>
  );
}
