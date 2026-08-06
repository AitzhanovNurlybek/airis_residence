"use client";

import { useRef, useState } from "react";

import { adminSend, AdminError } from "@/lib/adminClient";
import type { AdminRoom } from "@/lib/adminTypes";
import { AdminButton, useToast } from "@/components/admin/ui";

/**
 * Видеообзор номера.
 *
 * Ролик не идёт через наш сервер: у площадки запрос к функции ограничен
 * 4.5 МБ. Поэтому бэкенд выдаёт временную ссылку, браузер грузит файл
 * прямо в хранилище, и только потом мы подтверждаем загрузку.
 *
 * Если хранилище такие ссылки не выдаёт (обычный диск на своём сервере),
 * бэкенд отвечает 501, и мы грузим файл привычным способом — через API.
 */

const ACCEPT = "video/mp4,video/webm,video/quicktime";

type SignResponse = {
  uploadUrl: string;
  key: string;
  contentType: string;
  maxBytes: number;
};

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} МБ`
    : `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}

/** Загрузка с прогрессом. fetch о ходе отправки не сообщает, поэтому XHR. */
function putWithProgress(
  url: string,
  file: File,
  contentType: string,
  onProgress: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", contentType);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Хранилище отклонило файл (${xhr.status})`));
    xhr.onerror = () => reject(new Error("Обрыв связи при загрузке"));
    xhr.onabort = () => reject(new Error("Загрузка отменена"));

    xhr.send(file);
  });
}

export function VideoManager({
  slug,
  video,
  poster,
  onChange,
}: {
  slug: string;
  video: string;
  poster?: string;
  onChange: (video: string) => void;
}) {
  const [percent, setPercent] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const uploading = percent !== null;

  const reset = () => {
    setPercent(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  const upload = async (file: File) => {
    setPercent(0);
    try {
      let room: AdminRoom;
      try {
        const signed = await adminSend<SignResponse>(`/rooms/${slug}/video/sign`, "POST", {
          filename: file.name,
          contentType: file.type,
          sizeBytes: file.size,
        });

        await putWithProgress(signed.uploadUrl, file, signed.contentType, setPercent);
        setPercent(100);
        room = await adminSend<AdminRoom>(`/rooms/${slug}/video/confirm`, "POST", {
          key: signed.key,
        });
      } catch (e) {
        // 501 — хранилище без временных ссылок. Грузим через API.
        if (!(e instanceof AdminError) || e.status !== 501) throw e;

        const form = new FormData();
        form.append("file", file);
        const res = await fetch(`/api/admin/rooms/${slug}/video`, {
          method: "POST",
          body: form,
        });
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new AdminError(data?.detail ?? "Не удалось загрузить", res.status);
        }
        room = (await res.json()) as AdminRoom;
      }

      onChange(room.video);
      toast.show("Видео загружено");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Не удалось загрузить видео", "error");
    } finally {
      reset();
    }
  };

  const remove = async () => {
    if (!confirm("Удалить видеообзор этого номера?")) return;
    setBusy(true);
    try {
      const room = await adminSend<AdminRoom>(`/rooms/${slug}/video`, "DELETE");
      onChange(room.video);
      toast.show("Видео удалено");
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось удалить", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-card border border-white/10 bg-ink-900 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-xl text-cream">Видеообзор</h2>
        <p className="text-xs text-muted">MP4 до 40 МБ · лучше 15–30 секунд</p>
      </div>

      {video ? (
        <div className="mt-4">
          <video
            src={video}
            poster={poster}
            controls
            preload="metadata"
            playsInline
            className="w-full max-w-md rounded-xl border border-white/10 bg-ink-950"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <AdminButton
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={uploading || busy}
            >
              Заменить
            </AdminButton>
            <AdminButton type="button" onClick={remove} disabled={uploading || busy}>
              Удалить
            </AdminButton>
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <p className="text-sm leading-relaxed text-muted">
            Короткий проход по номеру убеждает лучше любых слов. Снимите горизонтально,
            при свете дня, без резких движений.
          </p>
          <AdminButton
            type="button"
            className="mt-3"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            Загрузить видео
          </AdminButton>
        </div>
      )}

      {uploading && (
        <div className="mt-4">
          <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
            <div
              className="h-full rounded-full bg-sand-400 transition-[width] duration-200"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-muted">
            {percent < 100 ? `Загрузка… ${percent}%` : "Проверяем файл…"}
          </p>
        </div>
      )}

      <input
        ref={fileInput}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          // Отсекаем заведомо большой файл здесь: иначе гость загрузчика
          // прождёт всю отправку, чтобы получить отказ в конце.
          if (file.size > 40 * 1024 * 1024) {
            toast.show(
              `Файл ${formatSize(file.size)} — это больше 40 МБ. Сожмите ролик или снимите короче.`,
              "error",
            );
            reset();
            return;
          }
          void upload(file);
        }}
      />
    </section>
  );
}
