import Link from "next/link";
import { buttonClass } from "@/components/ui/Button";

export default function NotFoundEn() {
  return (
    <div className="container-page grid min-h-[70svh] place-items-center py-24 text-center">
      <div>
        <p className="eyebrow">Error 404</p>
        <h1 className="mt-5 font-display text-[clamp(2.4rem,6vw,4rem)] leading-[1.05] font-semibold text-cream">
          Page not found
        </h1>
        <p className="mx-auto mt-5 max-w-md leading-relaxed text-muted">
          The page may have moved, or there is a typo in the address. Go back to the home page or see
          our rooms.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          <Link href="/en" className={buttonClass("primary", "lg")}>
            Home page
          </Link>
          <Link href="/en/rooms" className={buttonClass("outline", "lg")}>
            See rooms
          </Link>
        </div>
      </div>
    </div>
  );
}
