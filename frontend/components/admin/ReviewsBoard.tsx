"use client";

import { useState } from "react";

import { AdminButton, useToast } from "@/components/admin/ui";
import { adminSend, AdminError } from "@/lib/adminClient";
import type { AdminReview } from "@/lib/adminTypes";
import { hotelDateTime } from "@/lib/almaty";

const STATUS: Record<AdminReview["status"], { label: string; tone: string }> = {
  pending: { label: "Ждёт проверки", tone: "bg-sand-300/20 text-sand-200" },
  published: { label: "На сайте", tone: "bg-emerald-500/15 text-emerald-300" },
  hidden: { label: "Скрыт", tone: "bg-white/10 text-muted" },
};

/**
 * Проверка отзывов с сайта. На сайте отзыв появляется, только когда его
 * опубликуют здесь: открытая форма без проверки быстро обрастает спамом.
 * Жалобу не прячем молча — сначала ответить гостю (контакт в карточке).
 */
export function ReviewsBoard({ initialReviews }: { initialReviews: AdminReview[] }) {
  const [reviews, setReviews] = useState(initialReviews);
  const [busy, setBusy] = useState<number | null>(null);
  const toast = useToast();

  async function setStatus(review: AdminReview, status: AdminReview["status"]) {
    setBusy(review.id);
    try {
      const saved = await adminSend<AdminReview>(`/reviews/${review.id}`, "PATCH", { status });
      setReviews((list) => list.map((r) => (r.id === saved.id ? saved : r)));
      toast.show(status === "published" ? "Опубликован на сайте" : status === "hidden" ? "Скрыт" : "Вернули на проверку");
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось сохранить", "error");
    } finally {
      setBusy(null);
    }
  }

  async function remove(review: AdminReview) {
    if (!confirm("Удалить отзыв совсем? Для настоящего отзыва лучше «Скрыть».")) return;
    setBusy(review.id);
    try {
      await adminSend(`/reviews/${review.id}`, "DELETE");
      setReviews((list) => list.filter((r) => r.id !== review.id));
      toast.show("Отзыв удалён");
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось удалить", "error");
    } finally {
      setBusy(null);
    }
  }

  const pending = reviews.filter((r) => r.status === "pending").length;

  return (
    <div className="mx-auto max-w-4xl px-5 py-10 md:px-8">
      <h1 className="font-display text-3xl text-cream">Отзывы с сайта</h1>
      <p className="mt-2 text-sm text-muted">
        {pending ? `Ждут проверки: ${pending}. ` : "Новых нет. "}
        На сайте видны только опубликованные. Контакт гостя не публикуется.
      </p>

      {reviews.length === 0 && <p className="mt-10 text-muted">Отзывов пока нет.</p>}

      <ul className="mt-8 space-y-4">
        {reviews.map((review) => (
          <li key={review.id} className="rounded-2xl border border-white/10 bg-ink-900 p-5">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="text-sand-400">{"★".repeat(review.stars)}<span className="text-white/15">{"★".repeat(5 - review.stars)}</span></span>
              <span className="text-cream">{review.name}</span>
              {review.stay && <span className="text-muted">· {review.stay}</span>}
              <span className={`rounded-full px-2.5 py-0.5 text-xs ${STATUS[review.status].tone}`}>{STATUS[review.status].label}</span>
              <span className="ml-auto text-xs text-muted">{hotelDateTime.format(new Date(review.created_at))}</span>
            </div>
            <p className="mt-3 whitespace-pre-line text-[0.95rem] leading-relaxed text-cream/85">{review.text}</p>
            {review.contact && <p className="mt-2 text-sm text-muted">Контакт: {review.contact}</p>}
            <div className="mt-4 flex flex-wrap gap-2">
              {review.status !== "published" && (
                <AdminButton disabled={busy === review.id} onClick={() => setStatus(review, "published")}>
                  Опубликовать
                </AdminButton>
              )}
              {review.status !== "hidden" && (
                <AdminButton variant="secondary" disabled={busy === review.id} onClick={() => setStatus(review, "hidden")}>
                  Скрыть
                </AdminButton>
              )}
              <AdminButton variant="danger" disabled={busy === review.id} onClick={() => remove(review)}>
                Удалить
              </AdminButton>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
