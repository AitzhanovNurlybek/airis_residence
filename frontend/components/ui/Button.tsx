import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type Variant = "primary" | "ghost" | "outline";
type Size = "md" | "lg";

// Переход перечисляет свойства поимённо: с `transition-all` браузер следит
// за всеми, включая те, что не меняются. Длительность 200 мс вместо 300 —
// интерфейсная анимация должна укладываться в 300, а кнопка нажимается чаще
// всего остального. `active:scale-[0.97]` — отклик на нажатие: без него на
// телефоне палец не получает вообще никакого подтверждения, что кнопка
// услышала. Ховер-эффекты спрятаны за `hover:hover`, иначе на тач-экране
// подъём срабатывает от тапа и залипает после отпускания.
const base =
  "group relative inline-flex items-center justify-center gap-2.5 rounded-full font-medium tracking-wide " +
  "transition-[transform,box-shadow,background-color,border-color,color] duration-200 ease-airis " +
  "active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50";

const variants: Record<Variant, string> = {
  primary:
    "bg-linear-to-b from-wine-500 to-wine-700 text-white shadow-[0_10px_30px_-10px_rgba(160,26,84,0.9)] can-hover:hover:from-wine-400 can-hover:hover:to-wine-600 can-hover:hover:shadow-[0_16px_44px_-12px_rgba(184,41,106,0.95)] can-hover:hover:-translate-y-0.5",
  outline:
    "border border-sand-400/35 text-sand-100 can-hover:hover:border-sand-300/70 can-hover:hover:bg-sand-300/8 can-hover:hover:-translate-y-0.5",
  ghost: "text-cream/80 can-hover:hover:text-cream can-hover:hover:bg-white/6",
};

const sizes: Record<Size, string> = {
  md: "h-11 px-6 text-sm",
  lg: "h-14 px-9 text-[0.95rem]",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra = "") {
  return `${base} ${variants[variant]} ${sizes[size]} ${extra}`;
}

type ButtonProps = {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
  className?: string;
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  ...rest
}: ButtonProps & ComponentProps<"button">) {
  return (
    <button className={buttonClass(variant, size, className)} {...rest}>
      {children}
    </button>
  );
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className = "",
  children,
  href,
  ...rest
}: ButtonProps & ComponentProps<typeof Link>) {
  return (
    <Link href={href} className={buttonClass(variant, size, className)} {...rest}>
      {children}
    </Link>
  );
}
