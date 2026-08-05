import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type Variant = "primary" | "ghost" | "outline";
type Size = "md" | "lg";

const base =
  "group relative inline-flex items-center justify-center gap-2.5 rounded-full font-medium tracking-wide transition-all duration-300 ease-out disabled:pointer-events-none disabled:opacity-50";

const variants: Record<Variant, string> = {
  primary:
    "bg-linear-to-b from-wine-500 to-wine-700 text-white shadow-[0_10px_30px_-10px_rgba(160,26,84,0.9)] hover:from-wine-400 hover:to-wine-600 hover:shadow-[0_16px_44px_-12px_rgba(184,41,106,0.95)] hover:-translate-y-0.5 active:translate-y-0",
  outline:
    "border border-sand-400/35 text-sand-100 hover:border-sand-300/70 hover:bg-sand-300/8 hover:-translate-y-0.5",
  ghost: "text-cream/80 hover:text-cream hover:bg-white/6",
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
