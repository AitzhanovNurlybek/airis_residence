import { amenities } from "@/lib/site";
import { amenityIcons } from "@/components/ui/Icons";
import { SectionHead } from "@/components/ui/SectionHead";
import { Reveal } from "@/components/ui/Reveal";

export function Amenities() {
  return (
    <section className="relative py-16 md:py-28">
      <div className="container-page">
        <SectionHead
          eyebrow="Что входит"
          title="Услуги отеля"
          description="Без скрытых доплат: всё перечисленное входит в стоимость проживания."
          align="center"
        />

        {/* На телефоне две колонки: восемь строк подряд читаются как список дел */}
        <div className="mt-10 grid grid-cols-2 gap-px overflow-hidden rounded-card border border-white/8 bg-white/8 md:mt-14 lg:grid-cols-4">
          {amenities.map((item, i) => {
            const Icon = amenityIcons[item.icon];
            return (
              <Reveal key={item.title} delay={(i % 4) * 0.06} depth={false}>
                <div className="group h-full bg-ink-900 p-5 transition-colors duration-500 hover:bg-ink-800 md:p-7">
                  <span className="grid size-10 place-items-center rounded-xl border border-sand-400/25 bg-sand-400/8 text-sand-300 transition-all duration-500 group-hover:scale-110 group-hover:border-sand-300/50 group-hover:text-sand-200 md:size-12 md:rounded-2xl">
                    {Icon && <Icon className="size-5 md:size-6" />}
                  </span>
                  <h3 className="mt-4 text-[0.92rem] font-medium text-cream md:mt-5 md:text-base">
                    {item.title}
                  </h3>
                  <p className="mt-1.5 text-[0.8rem] leading-relaxed text-muted md:mt-2 md:text-sm">
                    {item.note}
                  </p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
