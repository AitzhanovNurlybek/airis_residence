import { nearby, site } from "@/lib/site";
import { SectionHead } from "@/components/ui/SectionHead";
import { Reveal } from "@/components/ui/Reveal";
import { IconClock, IconMail, IconPhone, IconPin } from "@/components/ui/Icons";

/**
 * Карта грузится статичным iframe без API-ключа.
 * Адрес и телефоны дублируются текстом рядом с картой — это то,
 * что читают поисковики и что попадает в локальную выдачу.
 */
export function Location() {
  const mapSrc = `https://maps.google.com/maps?q=${site.address.lat},${site.address.lng}&z=16&output=embed&hl=ru`;

  return (
    <section id="raspolozhenie" className="relative scroll-mt-24 py-20 md:py-32">
      <div className="container-page">
        <SectionHead
          eyebrow="Расположение"
          title="Алмалинский район, 800 м до проспекта Абая"
          description="Отель стоит в тихом месте, но всё нужное — рядом: метро, театры, музеи и деловой центр города."
        />

        <div className="mt-10 grid gap-7 md:mt-14 md:gap-8 lg:grid-cols-[1.15fr_1fr] lg:gap-10">
          <Reveal className="order-2 lg:order-1">
            <div className="h-full overflow-hidden rounded-card border border-white/10 shadow-deep">
              <iframe
                src={mapSrc}
                title={`Карта: ${site.name}, ${site.address.full}`}
                className="h-[22rem] w-full lg:h-full lg:min-h-[28rem]"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                style={{ border: 0, filter: "grayscale(0.35) contrast(1.05)" }}
              />
            </div>
          </Reveal>

          <div className="order-1 space-y-8 lg:order-2">
            <Reveal direction="right">
              <div className="rounded-card border border-white/10 bg-ink-900 p-6 md:p-7">
                <address className="space-y-5 text-sm not-italic">
                  <a
                    href={site.address.mapUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex gap-3.5 transition-colors hover:text-sand-300"
                  >
                    <IconPin className="mt-0.5 size-5 shrink-0 text-sand-400" />
                    <span>
                      <span className="block text-cream">{site.address.street}</span>
                      <span className="mt-1 block text-muted">
                        г. {site.address.city}, Алмалинский район
                      </span>
                    </span>
                  </a>

                  <div className="hairline" />

                  <a
                    href={`tel:${site.contacts.phonePrimaryRaw}`}
                    className="flex gap-3.5 text-cream transition-colors hover:text-sand-300"
                  >
                    <IconPhone className="mt-0.5 size-5 shrink-0 text-sand-400" />
                    {site.contacts.phonePrimary}
                  </a>
                  <a
                    href={`tel:${site.contacts.phoneCityRaw}`}
                    className="flex gap-3.5 text-cream transition-colors hover:text-sand-300"
                  >
                    <IconPhone className="mt-0.5 size-5 shrink-0 text-sand-400" />
                    {site.contacts.phoneCity}
                  </a>
                  <a
                    href={`mailto:${site.contacts.email}`}
                    className="flex gap-3.5 break-all text-cream transition-colors hover:text-sand-300"
                  >
                    <IconMail className="mt-0.5 size-5 shrink-0 text-sand-400" />
                    {site.contacts.email}
                  </a>
                  <p className="flex gap-3.5 text-muted">
                    <IconClock className="mt-0.5 size-5 shrink-0 text-sand-400" />
                    {site.contacts.hours}
                  </p>
                </address>
              </div>
            </Reveal>

            <Reveal direction="right" delay={0.1}>
              <div>
                <h3 className="eyebrow">Рядом с отелем</h3>
                <ul className="mt-5 divide-y divide-white/8">
                  {nearby.map((place) => (
                    <li
                      key={place.name}
                      className="flex items-baseline justify-between gap-6 py-3.5 text-sm"
                    >
                      <span className="text-cream/85">{place.name}</span>
                      <span className="shrink-0 text-right">
                        <span className="block text-sand-400 tabular-nums">{place.distance}</span>
                        {place.walk && (
                          <span className="mt-0.5 block text-xs text-muted">{place.walk}</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          </div>
        </div>
      </div>
    </section>
  );
}
