"use client";

import { useRef, useState } from "react";

import { adminSend, AdminError } from "@/lib/adminClient";
import { AdminButton, useToast } from "@/components/admin/ui";

/**
 * Загрузка видеообзора. Общий блок: используется и у номера,
 * и у роликов на главной — отличаются только адресом в API.
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
  posterUploadUrl: string;
  posterKey: string;
  posterContentType: string;
};

/**
 * Вырезает кадр из выбранного файла прямо в браузере.
 *
 * Нужен, чтобы до нажатия play показывать настоящий кадр, а не грузить
 * ролик ради превью и не подставлять фотографию номера: снимают
 * вертикально, а фото горизонтальные.
 *
 * Не получилось — не беда, вернём null и обойдёмся без заставки.
 */
function grabPoster(file: File): Promise<Blob | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    let done = false;

    const finish = (blob: Blob | null) => {
      if (done) return;
      done = true;
      URL.revokeObjectURL(url);
      resolve(blob);
    };

    // Кадр берём на второй секунде: первый кадр часто смазан движением руки.
    video.onloadedmetadata = () => {
      video.currentTime = Math.min(2, (video.duration || 0) / 3);
    };
    video.onseeked = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d")?.drawImage(video, 0, 0);
        canvas.toBlob((blob) => finish(blob), "image/jpeg", 0.75);
      } catch {
        finish(null);
      }
    };
    video.onerror = () => finish(null);
    // Кодек, который браузер не играет (HEVC с айфона), кадр не отдаст.
    setTimeout(() => finish(null), 10_000);

    video.preload = "metadata";
    video.muted = true;
    video.src = url;
  });
}

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

export function VideoManager<T extends { video: string; videoPoster: string }>({
  endpoint,
  video,
  poster,
  hint,
  onChange,
}: {
  /** Путь к сущности в админском API: /rooms/standart, /site-videos/kitchen */
  endpoint: string;
  video: string;
  poster: string;
  hint?: string;
  onChange: (item: T) => void;
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
      let item: T;
      try {
        const signed = await adminSend<SignResponse>(`${endpoint}/video/sign`, "POST", {
          filename: file.name,
          contentType: file.type,
          sizeBytes: file.size,
        });

        await putWithProgress(signed.uploadUrl, file, signed.contentType, setPercent);
        setPercent(100);

        // Заставка необязательна: не вышло — плеер просто будет без картинки.
        let posterKey: string | null = null;
        const posterBlob = await grabPoster(file);

        // Кадр не вырезался — значит браузер не смог прочитать файл.
        // Чаще всего это HEVC с айфона: Safari его играет, Chrome нет.
        // Промолчать нельзя: ролик загрузится, а половина гостей увидит
        // чёрный прямоугольник, и никто об этом не узнает.
        if (!posterBlob) {
          toast.show(
            "Браузер не смог прочитать этот файл — скорее всего это HEVC с айфона. " +
              "У части гостей видео не откроется. Лучше пересохранить ролик в MP4 (H.264).",
            "error",
          );
        }

        if (posterBlob && signed.posterUploadUrl) {
          try {
            await putWithProgress(
              signed.posterUploadUrl,
              new File([posterBlob], "poster.jpg", { type: "image/jpeg" }),
              signed.posterContentType,
              () => {},
            );
            posterKey = signed.posterKey;
          } catch {
            posterKey = null;
          }
        }

        item = await adminSend<T>(`${endpoint}/video/confirm`, "POST", {
          key: signed.key,
          posterKey,
        });
      } catch (e) {
        // 501 — хранилище без временных ссылок. Грузим через API.
        if (!(e instanceof AdminError) || e.status !== 501) throw e;

        const form = new FormData();
        form.append("file", file);
        const res = await fetch(`/api/admin${endpoint}/video`, {
          method: "POST",
          body: form,
        });
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new AdminError(data?.detail ?? "Не удалось загрузить", res.status);
        }
        item = (await res.json()) as T;
      }

      onChange(item);
      toast.show("Видео загружено");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Не удалось загрузить видео", "error");
    } finally {
      reset();
    }
  };

  const remove = async () => {
    if (!confirm("Удалить этот видеообзор?")) return;
    setBusy(true);
    try {
      const item = await adminSend<T>(`${endpoint}/video`, "DELETE");
      onChange(item);
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
        <p className="text-xs text-muted">{hint ?? "MP4 до 40 МБ · лучше 15–30 секунд"}</p>
      </div>

      {video ? (
        <div className="mt-4">
          {/* Ролики снимают и вертикально, и горизонтально — ограничиваем
              по высоте, чтобы вертикальный не растянул полстраницы. */}
          <video
            src={video}
            poster={poster || undefined}
            controls
            preload="metadata"
            playsInline
            className="max-h-[60vh] w-auto max-w-full rounded-xl border border-white/10 bg-ink-950"
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
