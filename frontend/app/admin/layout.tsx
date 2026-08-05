import type { Metadata } from "next";
import Link from "next/link";

import { ToastProvider } from "@/components/admin/ui";
import { AdminNav } from "@/components/admin/AdminNav";
import { BACKEND } from "@/lib/adminServer";

export const metadata: Metadata = {
  title: "Управление сайтом",
  robots: { index: false, follow: false },
};

// Админку нельзя кешировать и нельзя пререндерить при сборке:
// её содержимое зависит от того, кто вошёл.
export const dynamic = "force-dynamic";

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  if (!BACKEND) {
    return (
      <div className="grid min-h-dvh place-items-center px-5">
        <div className="max-w-lg text-center">
          <h1 className="font-display text-3xl text-cream">Админка не подключена</h1>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            Чтобы редактировать номера, нужен бэкенд. Запустите его
            (<code className="text-sand-300">backend/</code>) и укажите его адрес
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

  return (
    <ToastProvider>
      <div className="min-h-dvh bg-ink-950">
        <AdminNav />
        <div className="mx-auto max-w-6xl px-5 py-8 pb-28 md:px-8 md:py-10">{children}</div>
      </div>
    </ToastProvider>
  );
}
