import Link from "next/link";

import { site, type Room } from "@/lib/site";
import { rooms as fallbackRooms } from "@/lib/site";
import { Logo } from "@/components/ui/Logo";
import { IconClock, IconMail, IconPhone, IconPin, IconTelegram, IconWhatsApp } from "@/components/ui/Icons";

const legalLinks = [
  { href: "/o-kompanii", label: "О компании" },
  { href: "/kontakty", label: "Контакты" },
  { href: "/kak-oplatit", label: "Как оплатить" },
  { href: "/oferta", label: "Публичная оферта" },
  { href: "/politika-konfidencialnosti", label: "Политика конфиденциальности" },
];

export function Footer({ rooms = fallbackRooms }: { rooms?: Room[] }) {
  return (
    <footer className="relative mt-20 overflow-hidden border-t border-white/8 bg-ink-900 md:mt-32">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-80 w-[42rem] -translate-x-1/2 rounded-full bg-wine-700/22 blur-[120px]" />
      <span className="grain-layer" />

      <div className="container-page relative py-12 md:py-20">
        <div className="grid gap-10 sm:grid-cols-2 md:gap-12 lg:grid-cols-[1.3fr_1fr_1fr_1.1fr]">
          <div className="sm:col-span-2 lg:col-span-1">
            <Logo className="h-11 w-auto" />
            <p className="mt-5 max-w-xs text-sm leading-relaxed text-muted">
              Отель на {site.roomsCount} номеров в центре Алматы. Завтрак включён, стойка
              регистрации работает круглосуточно.
            </p>
            <div className="mt-6 flex gap-3 be-socials">
              <a
                href={site.contacts.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Написать в WhatsApp"
                className="glass grid size-11 place-items-center rounded-full text-cream transition-colors hover:text-[#25D366]"
              >
                <IconWhatsApp className="size-5" />
              </a>
              <a
                href={site.contacts.telegram}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Написать в Telegram"
                className="glass grid size-11 place-items-center rounded-full text-cream transition-colors hover:text-[#29a9eb]"
              >
                <IconTelegram className="size-5" />
              </a>
            </div>
          </div>

          <nav aria-label="Номера">
            <h2 className="eyebrow">Номера</h2>
            <ul className="mt-5 space-y-3 text-sm">
              {rooms.map((room) => (
                <li key={room.slug}>
                  <Link
                    href={`/nomera/${room.slug}`}
                    className="text-cream/75 transition-colors hover:text-sand-300"
                  >
                    {room.shortName}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Информация">
            <h2 className="eyebrow">Информация</h2>
            <ul className="mt-5 space-y-3 text-sm">
              {/* Корпоративный раздел — сначала объяснение, потом вход:
                  ссылка «Кабинет» в подвале отеля читается как служебная. */}
              <li>
                <Link
                  href="/korporativnym-klientam"
                  className="text-cream/75 transition-colors hover:text-sand-300"
                >
                  Корпоративным клиентам
                </Link>
              </li>
              {legalLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-cream/75 transition-colors hover:text-sand-300"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <h2 className="eyebrow">Контакты</h2>
            <address className="mt-5 space-y-4 text-sm not-italic">
              <a
                href={site.address.mapUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-11 items-center gap-3 py-1 text-cream/75 transition-colors can-hover:hover:text-sand-300"
              >
                <IconPin className="mt-0.5 size-4 shrink-0 text-sand-400" />
                <span>
                  г. {site.address.city}, {site.address.street}
                </span>
              </a>
              <a
                href={`tel:${site.contacts.phonePrimaryRaw}`}
                className="flex min-h-11 items-center gap-3 py-1 text-cream/75 transition-colors can-hover:hover:text-sand-300"
              >
                <IconPhone className="mt-0.5 size-4 shrink-0 text-sand-400" />
                {site.contacts.phonePrimary}
              </a>
              <a
                href={`tel:${site.contacts.phoneCityRaw}`}
                className="flex min-h-11 items-center gap-3 py-1 text-cream/75 transition-colors can-hover:hover:text-sand-300"
              >
                <IconPhone className="mt-0.5 size-4 shrink-0 text-sand-400" />
                {site.contacts.phoneCity}
              </a>
              <a
                href={`mailto:${site.contacts.email}`}
                className="flex min-h-11 items-center gap-3 py-1 break-all text-cream/75 transition-colors can-hover:hover:text-sand-300"
              >
                <IconMail className="mt-0.5 size-4 shrink-0 text-sand-400" />
                {site.contacts.email}
              </a>
              <p className="flex gap-3 text-cream/75">
                <IconClock className="mt-0.5 size-4 shrink-0 text-sand-400" />
                {site.contacts.hours}
              </p>
            </address>
          </div>
        </div>

        <div className="hairline my-10 md:my-12" />

        <div className="flex flex-col gap-4 text-xs text-muted md:flex-row md:items-start md:justify-between">
          <p className="max-w-2xl leading-relaxed">
            {site.legalName}, БИН {site.legal.bin}. Юр. адрес: {site.address.full}. ИИК{" "}
            {site.legal.iik}, БИК {site.legal.bik}, {site.legal.bank}, КБе {site.legal.kbe}.
          </p>
          <p className="shrink-0">© {new Date().getFullYear()} {site.name}</p>
        </div>
      </div>
    </footer>
  );
}
