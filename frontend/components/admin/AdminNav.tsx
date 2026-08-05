"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { adminLogout } from "@/lib/adminClient";
import { Logo } from "@/components/ui/Logo";

const links = [
  { href: "/admin", label: "Номера" },
  { href: "/admin/zayavki", label: "Заявки" },
];

export function AdminNav() {
  const pathname = usePathname();
  if (pathname === "/admin/login") return null;

  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-ink-950/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3 md:px-8">
        <div className="flex items-center gap-6">
          <Logo className="h-7 w-auto" withMark={false} />
          <nav className="flex gap-1">
            {links.map((link) => {
              const active =
                link.href === "/admin"
                  ? pathname === "/admin" || pathname.startsWith("/admin/nomera")
                  : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-full px-4 py-2 text-sm transition-colors ${
                    active ? "bg-white/8 text-cream" : "text-muted hover:text-cream"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/"
            target="_blank"
            className="hidden rounded-full px-4 py-2 text-sm text-muted transition-colors hover:text-cream sm:block"
          >
            Открыть сайт ↗
          </Link>
          <button
            type="button"
            onClick={adminLogout}
            className="rounded-full px-4 py-2 text-sm text-muted transition-colors hover:text-wine-200"
          >
            Выйти
          </button>
        </div>
      </div>
    </header>
  );
}
