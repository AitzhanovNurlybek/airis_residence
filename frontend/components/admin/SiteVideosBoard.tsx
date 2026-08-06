"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { adminSend, AdminError } from "@/lib/adminClient";
import type { AdminSiteVideo } from "@/lib/siteVideoTypes";
import { AdminButton, Field, inputClass, useToast } from "@/components/admin/ui";
import { VideoManager } from "@/components/admin/VideoManager";

/**
 * Видеообзоры на главной: кухня, лобби, общие зоны.
 *
 * От видео у номера отличается только тем, что ролик сам по себе:
 * у него свой заголовок и своё место в блоке. Загрузка общая.
 */

function slugify(value: string): string {
  const map: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z",
    и: "i", й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r",
    с: "s", т: "t", у: "u", ф: "f", х: "h", ц: "c", ч: "ch", ш: "sh", щ: "sch",
    ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
  };
  return value
    .toLowerCase()
    .split("")
    .map((ch) => map[ch] ?? ch)
    .join("")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 58);
}

export function SiteVideosBoard({ items: initial }: { items: AdminSiteVideo[] }) {
  const [items, setItems] = useState(initial);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const toast = useToast();
  const router = useRouter();

  const replace = (updated: AdminSiteVideo) =>
    setItems((prev) => prev.map((it) => (it.slug === updated.slug ? updated : it)));

  const create = async () => {
    const clean = title.trim();
    if (clean.length < 2) {
      toast.show("Напишите название — например «Кухня и завтраки»", "error");
      return;
    }
    const slug = slugify(clean) || `video-${Date.now()}`;

    setCreating(true);
    try {
      const item = await adminSend<AdminSiteVideo>("/site-videos", "POST", {
        slug,
        title: clean,
        summary: "",
      });
      setItems((prev) => [...prev, item]);
      setTitle("");
      toast.show("Блок создан — теперь загрузите ролик");
      router.refresh();
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось создать", "error");
    } finally {
      setCreating(false);
    }
  };

  const patch = async (slug: string, body: Partial<AdminSiteVideo>) => {
    try {
      const item = await adminSend<AdminSiteVideo>(`/site-videos/${slug}`, "PATCH", body);
      replace(item);
      router.refresh();
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось сохранить", "error");
    }
  };

  const remove = async (item: AdminSiteVideo) => {
    if (!confirm(`Удалить «${item.title}» вместе с роликом?`)) return;
    try {
      await adminSend(`/site-videos/${item.slug}`, "DELETE");
      setItems((prev) => prev.filter((it) => it.slug !== item.slug));
      toast.show("Удалено");
      router.refresh();
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось удалить", "error");
    }
  };

  return (
    <div>
      <h1 className="font-display text-3xl text-cream md:text-4xl">Видео на главной</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
        Ролики про отель целиком: кухня, лобби, общие зоны. Показываются на главной
        отдельным блоком. Видео конкретного номера загружается на странице этого номера.
      </p>

      {/* ---------- Добавить ---------- */}
      <section className="mt-8 rounded-card border border-white/10 bg-ink-900 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Название нового блока" hint="Например: Кухня и завтраки">
            <input
              className={`${inputClass} min-w-[16rem]`}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && create()}
            />
          </Field>
          <AdminButton type="button" onClick={create} disabled={creating}>
            Добавить
          </AdminButton>
        </div>
      </section>

      {/* ---------- Список ---------- */}
      {items.length === 0 ? (
        <p className="mt-8 text-sm text-muted">
          Пока ни одного ролика. Добавьте блок выше — и загрузите в него видео.
        </p>
      ) : (
        <div className="mt-8 space-y-8">
          {items.map((item) => (
            <article key={item.slug} className="rounded-card border border-white/10 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-[16rem] flex-1 space-y-4">
                  <Field label="Заголовок">
                    <input
                      className={inputClass}
                      defaultValue={item.title}
                      onBlur={(e) =>
                        e.target.value !== item.title &&
                        patch(item.slug, { title: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Подпись под видео" hint="Необязательно, одна строка">
                    <input
                      className={inputClass}
                      defaultValue={item.summary}
                      onBlur={(e) =>
                        e.target.value !== item.summary &&
                        patch(item.slug, { summary: e.target.value })
                      }
                    />
                  </Field>
                </div>

                <div className="flex flex-col items-end gap-2">
                  <button
                    type="button"
                    onClick={() => patch(item.slug, { isPublished: !item.isPublished })}
                    className={`rounded-full border px-4 py-2.5 text-sm transition-colors ${
                      item.isPublished
                        ? "border-emerald-400/40 text-emerald-200"
                        : "border-white/20 text-muted"
                    }`}
                  >
                    {item.isPublished ? "Виден на сайте" : "Скрыт с сайта"}
                  </button>
                  <AdminButton variant="quiet" type="button" onClick={() => remove(item)}>
                    Удалить блок
                  </AdminButton>
                </div>
              </div>

              <div className="mt-5">
                <VideoManager<AdminSiteVideo>
                  endpoint={`/site-videos/${item.slug}`}
                  video={item.video}
                  poster={item.videoPoster}
                  onChange={replace}
                />
              </div>

              {!item.video && (
                <p className="mt-3 text-xs text-muted">
                  Пока ролик не загружен, блок на сайте не показывается.
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
