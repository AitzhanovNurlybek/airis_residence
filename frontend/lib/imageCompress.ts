"use client";

/**
 * Сжатие фотографии до отправки, прямо в браузере.
 *
 * Зачем: у площадки жёсткий лимит 4.5 МБ на запрос к функции
 * (FUNCTION_PAYLOAD_TOO_LARGE). Снимок с телефона весит 3–12 МБ и
 * не доезжает даже до нашего кода — сотрудник видит «Ошибка 413»
 * и не может понять, что не так. Сервер при этом умеет ужимать
 * фотографии, но получить их ему неоткуда.
 *
 * Поэтому ужимаем здесь: 12 МБ превращаются в 200–400 КБ, и дальше
 * всё идёт по обычному пути. Сервер всё равно пережимает второй раз —
 * это дёшево и страхует от файлов, пришедших в обход админки.
 */

/** Совпадает с IMAGE_MAX_WIDTH на бэкенде: шире сайту не нужно. */
const MAX_SIDE = 2200;
const QUALITY = 0.82;

export type CompressResult = {
  file: File;
  /** Не удалось прочитать файл — отправляем как есть. */
  untouched: boolean;
};

export async function compressImage(file: File): Promise<CompressResult> {
  try {
    // imageOrientation: браузер сам применит поворот из EXIF, иначе
    // снятое телефоном фото ляжет боком.
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });

    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    if (!ctx) return { file, untouched: true };
    ctx.drawImage(bitmap, 0, 0, width, height);
    bitmap.close();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/webp", QUALITY),
    );
    if (!blob) return { file, untouched: true };

    // Крошечный файл сжимать незачем — оригинал может оказаться лучше.
    if (blob.size >= file.size) return { file, untouched: true };

    const name = file.name.replace(/\.[^.]+$/, "") + ".webp";
    return {
      file: new File([blob], name, { type: "image/webp", lastModified: file.lastModified }),
      untouched: false,
    };
  } catch {
    // Формат, который браузер не умеет открыть (например, HEIC в старом
    // браузере). Отправим оригинал: если он влезет в лимит — пройдёт.
    return { file, untouched: true };
  }
}
