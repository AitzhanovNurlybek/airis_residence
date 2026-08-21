import type { Metadata } from "next";
import Link from "next/link";

import { BACKEND } from "@/lib/corp/server";

export const metadata: Metadata = {
  title: "Корпоративный раздел",
  // Кабинет закрыт паролем, и в поиске ему делать нечего — как и админке.
  robots: { index: false, follow: false },
};

// Содержимое зависит от того, кто вошёл: ни кэшировать, ни пререндерить.
export const dynamic = "force-dynamic";

export default function CorpLayout({ children }: LayoutProps<"/corp">) {
  if (!BACKEND) {
    return (
      <div className="grid min-h-dvh place-items-center bg-ink-950 px-5">
        <div className="max-w-lg text-center">
          <h1 className="font-display text-3xl text-cream">Кабинет не подключён</h1>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            Корпоративный раздел работает только вместе с бэкендом. Запустите его
            (<code className="text-sand-300">backend/</code>) и укажите адрес
            в <code className="text-sand-300">frontend/.env.local</code>:
          </p>
          <pre className="mt-4 overflow-x-auto rounded-xl border border-white/10 bg-ink-900 p-4 text-left text-xs text-sand-200">
            BACKEND_URL=http://localhost:8000
          </pre>
          <Link href="/" className="mt-6 inline-block text-sm text-sand-300 underline">
            Вернуться на сайт
          </Link>
        </div>
      </div>
    );
  }

  return <div className="min-h-dvh bg-sand-100 text-ink-950">{children}</div>;
}
