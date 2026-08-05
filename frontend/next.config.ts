import type { NextConfig } from "next";

/**
 * Фотографии, загруженные через админку, лежат на бэкенде и отдаются
 * с его домена. next/image оптимизирует только разрешённые источники,
 * поэтому домен бэкенда нужно указать явно.
 */
function mediaPatterns(): NonNullable<NextConfig["images"]>["remotePatterns"] {
  const sources = [process.env.BACKEND_URL, process.env.NEXT_PUBLIC_MEDIA_BASE].filter(
    Boolean,
  ) as string[];

  const patterns: NonNullable<NonNullable<NextConfig["images"]>["remotePatterns"]> = [];
  for (const source of sources) {
    try {
      const url = new URL(source);
      patterns.push({
        protocol: url.protocol.replace(":", "") as "http" | "https",
        hostname: url.hostname,
        port: url.port || undefined,
        pathname: "/media/**",
      });
    } catch {
      console.warn(`Не удалось разобрать адрес для фотографий: ${source}`);
    }
  }
  return patterns;
}

const nextConfig: NextConfig = {
  images: {
    remotePatterns: mediaPatterns(),
  },
};

export default nextConfig;
