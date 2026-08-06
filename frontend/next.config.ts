import type { NextConfig } from "next";

/**
 * Фотографии, загруженные через админку, лежат на бэкенде и отдаются
 * с его домена. next/image оптимизирует только разрешённые источники,
 * поэтому домен бэкенда нужно указать явно.
 */
function mediaPatterns(): NonNullable<NextConfig["images"]>["remotePatterns"] {
  // BACKEND_URL — когда фото лежат на диске бэкенда и отдаются им же.
  // NEXT_PUBLIC_MEDIA_BASE — когда включено S3-хранилище: там свой домен
  // и свои пути (rooms/...), а не /media/.
  const sources = [
    { url: process.env.BACKEND_URL, pathname: "/media/**" },
    { url: process.env.NEXT_PUBLIC_MEDIA_BASE, pathname: "/**" },
  ].filter((item) => Boolean(item.url));

  const patterns: NonNullable<NonNullable<NextConfig["images"]>["remotePatterns"]> = [];
  for (const source of sources) {
    try {
      const url = new URL(source.url as string);
      patterns.push({
        protocol: url.protocol.replace(":", "") as "http" | "https",
        hostname: url.hostname,
        port: url.port || undefined,
        pathname: source.pathname,
      });
    } catch {
      console.warn(`Не удалось разобрать адрес для фотографий: ${source.url}`);
    }
  }
  return patterns;
}

const nextConfig: NextConfig = {
  images: {
    remotePatterns: mediaPatterns(),
    // На Vercel проект собран как два сервиса (vercel.json), и в этом режиме
    // адрес /_next/image не поднимается — оптимизатор отдавал 404, а с ним
    // не грузилась ни одна фотография. Поэтому картинки отдаём как есть:
    // исходники в public/ заранее сжаты (ширина ≤1800, качество 82),
    // а фото из админки жмёт бэкенд (Pillow → WebP) при загрузке.
    unoptimized: true,
  },
};

export default nextConfig;
