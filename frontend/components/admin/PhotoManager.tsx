"use client";

import { useRef, useState } from "react";

import { adminSend, adminUpload, AdminError } from "@/lib/adminClient";
import { compressImage } from "@/lib/imageCompress";
import type { AdminRoom } from "@/lib/adminTypes";
import { AdminButton, useToast } from "@/components/admin/ui";
import { AdminThumb } from "@/components/admin/AdminThumb";

/**
 * Фотографии номера.
 *
 * Порядок важен: первая фотография — обложка, её видно в списке номеров
 * на сайте и в поисковой выдаче. Поэтому кнопка «Сделать обложкой»
 * вынесена отдельно, а не спрятана за перетаскиванием.
 *
 * Каждое действие сохраняется сразу — фотографии не ждут общей кнопки
 * «Сохранить», иначе легко потерять загруженное.
 */
export function PhotoManager({
  slug,
  images,
  onChange,
}: {
  slug: string;
  images: string[];
  onChange: (images: string[]) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const upload = async (files: FileList | File[]) => {
    const list = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (list.length === 0) return;

    setUploading(true);
    try {
      // Ужимаем до отправки: снимок с телефона в 12 МБ не пролезет
      // в лимит запроса и вернёт непонятную «Ошибку 413».
      const prepared = await Promise.all(list.map(compressImage));

      const stuck = prepared.filter((r) => r.untouched && r.file.size > 4 * 1024 * 1024);
      if (stuck.length > 0) {
        toast.show(
          `Не удалось открыть ${stuck.length === 1 ? "файл" : "файлы"} для сжатия, ` +
            "а без него он слишком большой. Пересохраните фото в JPG и попробуйте снова.",
          "error",
        );
        return;
      }

      const room = await adminUpload<AdminRoom>(
        `/rooms/${slug}/images`,
        prepared.map((r) => r.file),
      );
      onChange(room.images);
      toast.show(
        list.length === 1 ? "Фотография загружена" : `Загружено фотографий: ${list.length}`,
      );
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось загрузить", "error");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const save = async (next: string[], message: string) => {
    const previous = images;
    onChange(next); // показываем результат сразу, не дожидаясь ответа
    setBusy(true);
    try {
      const room = await adminSend<AdminRoom>(`/rooms/${slug}/images`, "PUT", next);
      onChange(room.images);
      toast.show(message);
    } catch (e) {
      onChange(previous);
      toast.show(e instanceof AdminError ? e.message : "Не удалось сохранить", "error");
    } finally {
      setBusy(false);
    }
  };

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= images.length) return;
    const next = [...images];
    [next[index], next[target]] = [next[target], next[index]];
    save(next, "Порядок фотографий обновлён");
  };

  const makeCover = (index: number) => {
    if (index === 0) return;
    const next = [...images];
    const [picked] = next.splice(index, 1);
    save([picked, ...next], "Обложка изменена");
  };

  const remove = (index: number) => {
    if (!confirm("Удалить эту фотографию? Действие необратимо.")) return;
    save(
      images.filter((_, i) => i !== index),
      "Фотография удалена",
    );
  };

  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-xl text-cream">Фотографии</h2>
          <p className="mt-1 text-sm text-muted">
            Первая фотография — обложка номера. Изменения сохраняются сразу.
          </p>
        </div>
        <AdminButton
          variant="secondary"
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={uploading}
        >
          {uploading ? "Готовим и загружаем…" : "Выбрать файлы"}
        </AdminButton>
      </div>

      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => e.target.files && upload(e.target.files)}
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          upload(e.dataTransfer.files);
        }}
        className={`mt-5 rounded-2xl border-2 border-dashed p-6 text-center transition-colors ${
          dragOver ? "border-sand-400/70 bg-sand-400/8" : "border-white/12"
        }`}
      >
        <p className="text-sm text-muted">
          Перетащите фотографии сюда или{" "}
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="text-sand-300 underline underline-offset-4"
          >
            выберите на компьютере
          </button>
        </p>
        <p className="mt-2 text-xs text-muted/80">
          JPG, PNG или WebP. Снимки с телефона ужимаются прямо здесь, перед отправкой —
          грузите как есть, ничего заранее уменьшать не нужно.
        </p>
      </div>

      {images.length > 0 && (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {images.map((src, index) => (
            <figure key={src} className="group">
              <div className="relative">
                <AdminThumb src={src} alt={`Фото ${index + 1}`} />
                {index === 0 && (
                  <span className="absolute top-2 left-2 rounded-full bg-wine-600 px-2.5 py-1 text-[0.6rem] tracking-wide text-white uppercase">
                    обложка
                  </span>
                )}
              </div>

              <div className="mt-2 flex items-center justify-between gap-1">
                <div className="flex gap-1">
                  <button
                    type="button"
                    aria-label="Сдвинуть влево"
                    disabled={index === 0 || busy}
                    onClick={() => move(index, -1)}
                    className="grid size-8 place-items-center rounded-lg border border-white/12 text-xs text-muted transition-colors hover:text-cream disabled:opacity-30"
                  >
                    ←
                  </button>
                  <button
                    type="button"
                    aria-label="Сдвинуть вправо"
                    disabled={index === images.length - 1 || busy}
                    onClick={() => move(index, 1)}
                    className="grid size-8 place-items-center rounded-lg border border-white/12 text-xs text-muted transition-colors hover:text-cream disabled:opacity-30"
                  >
                    →
                  </button>
                </div>

                <div className="flex gap-1">
                  {index !== 0 && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => makeCover(index)}
                      className="rounded-lg border border-white/12 px-2.5 py-1.5 text-[0.68rem] text-muted transition-colors hover:border-sand-400/50 hover:text-cream disabled:opacity-40"
                    >
                      Обложка
                    </button>
                  )}
                  <button
                    type="button"
                    aria-label="Удалить фотографию"
                    disabled={busy}
                    onClick={() => remove(index)}
                    className="grid size-8 place-items-center rounded-lg border border-white/12 text-xs text-muted transition-colors hover:border-wine-400/50 hover:text-wine-200 disabled:opacity-40"
                  >
                    ✕
                  </button>
                </div>
              </div>
            </figure>
          ))}
        </div>
      )}
    </section>
  );
}
