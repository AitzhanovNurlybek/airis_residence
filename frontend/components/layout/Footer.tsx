import Link from "next/link";

import { site, rooms as fallbackRooms, type Room } from "@/lib/site";
import { localePath, type Locale } from "@/lib/i18n/config";
import { t, type Dictionary } from "@/lib/i18n";
import { Logo } from "@/components/ui/Logo";
import {
  IconClock,
  IconMail,
  IconPhone,
  IconPin,
  IconTelegram,
  IconWhatsApp,
} from "@/components/ui/Icons";

export function Footer({
  locale,
  dict,
  rooms = fallbackRooms,
}: {
  locale: Locale;
  dict: Dictionary;
  rooms?: Room[];
}) {
  const legalLinks = [
    { href: "/o-kompanii", label: dict.footer.company },
    { href: "/kontakty", label: dict.footer.contacts },
    { href: "/kak-oplatit", label: dict.footer.payment },
    { href: "/oferta", label: dict.footer.offer },
    { href: "/politika-konfidencialnosti", label: dict.footer.privacy },
  ];

  return (
    <footer className="relative mt-20 overflow-hidden border-t border-white/8 bg-ink-900 md:mt-32">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-80 w-[42rem] -translate-x-1/2 rounded-full bg-wine-700/22 blur-[120px]" />
      <span className="grain-layer" />

      <div className="container-page relative py-12 md:py-20">
        <div className="grid gap-10 sm:grid-cols-2 md:gap-12 lg:grid-cols-[1.3fr_1fr_1fr_1.1fr]">
          <div className="sm:col-span-2 lg:col-span-1">
            <Logo className="h-11 w-auto" />
            <p className="mt-5 max-w-xs text-sm leading-relaxed text-muted">
              {t(dict.footer.tagline, { count: site.roomsCount })}
            </p>
            <div className="mt-6 flex gap-3">
              <a
                href={site.contacts.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="WhatsApp"
                className="glass grid size-11 place-items-center rounded-full text-cream transition-colors hover:text-[#25D366]"
              >
                <IconWhatsApp className="size-5" />
              </a>
              <a
                href={site.contacts.telegram}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Telegram"
                className="glass grid size-11 place-items-center rounded-full text-cream transition-colors hover:text-[#29a9eb]"
              >
                <IconTelegram className="size-5" />
              </a>
            </div>
          </div>

          <nav aria-label={dict.footer.rooms}>
            <h2 className="eyebrow">{dict.footer.rooms}</h2>
            <ul className="mt-5 space-y-3 text-sm">
              {rooms.map((room) => (
                <li key={room.slug}>
                  <Link
                    href={localePath(locale, `/nomera/${room.slug}`)}
                    className="text-cream/75 transition-colors hover:text-sand-300"
                  >
                    {room.shortName}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label={dict.footer.info}>
            <h2 className="eyebrow">{dict.footer.info}</h2>
            <ul className="mt-5 space-y-3 text-sm">
              {legalLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={localePath(locale, link.href)}
                    className="text-cream/75 transition-colors hover:text-sand-300"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <h2 className="eyebrow">{dict.footer.contacts}</h2>
            <address className="mt-5 space-y-4 text-sm not-italic">
              <a
                href={site.address.mapUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex gap-3 text-cream/75 transition-colors hover:text-sand-300"
              >
                <IconPin className="mt-0.5 size-4 shrink-0 text-sand-400" />
                <span>
                  {site.address.city}, {site.address.street}
                </span>
              </a>
              <a
                href={`tel:${site.contacts.phonePrimaryRaw}`}
                className="flex gap-3 text-cream/75 transition-colors hover:text-sand-300"
              >
                <IconPhone className="mt-0.5 size-4 shrink-0 text-sand-400" />
                {site.contacts.phonePrimary}
              </a>
              <a
                href={`tel:${site.contacts.phoneCityRaw}`}
                className="flex gap-3 text-cream/75 transition-colors hover:text-sand-300"
              >
                <IconPhone className="mt-0.5 size-4 shrink-0 text-sand-400" />
                {site.contacts.phoneCity}
              </a>
              <a
                href={`mailto:${site.contacts.email}`}
                className="flex gap-3 break-all text-cream/75 transition-colors hover:text-sand-300"
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
            {site.legalName}, БИН {site.legal.bin}. {site.address.full}. ИИК {site.legal.iik},
            БИК {site.legal.bik}, {site.legal.bank}, КБе {site.legal.kbe}.
          </p>
          <p className="shrink-0">
            © {new Date().getFullYear()} {site.name}
          </p>
        </div>
      </div>
    </footer>
  );
}
