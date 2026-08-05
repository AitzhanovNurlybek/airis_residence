import type { ReactNode } from "react";
import { Reveal } from "@/components/ui/Reveal";

export function SectionHead({
  eyebrow,
  title,
  description,
  align = "left",
  action,
}: {
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  align?: "left" | "center";
  action?: ReactNode;
}) {
  const centered = align === "center";
  return (
    <Reveal className={centered ? "text-center" : ""}>
      <div
        className={`flex flex-col gap-6 ${
          centered ? "items-center" : "md:flex-row md:items-end md:justify-between"
        }`}
      >
        <div className={centered ? "max-w-2xl" : "max-w-2xl"}>
          <p className="eyebrow">{eyebrow}</p>
          <h2 className="mt-4 font-display text-[clamp(2rem,4.4vw,3.35rem)] leading-[1.06] font-semibold tracking-[-0.02em] text-cream">
            {title}
          </h2>
          {description && (
            <p className="mt-5 text-base leading-relaxed text-muted md:text-[1.05rem]">
              {description}
            </p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </Reveal>
  );
}
