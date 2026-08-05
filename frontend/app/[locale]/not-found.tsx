import Link from "next/link";
import { buttonClass } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="container-page grid min-h-[70svh] place-items-center py-24 text-center">
      <div>
        <p className="eyebrow">Ошибка 404</p>
        <h1 className="mt-5 font-display text-[clamp(2.4rem,6vw,4rem)] leading-[1.05] font-semibold text-cream">
          Такой страницы нет
        </h1>
        <p className="mx-auto mt-5 max-w-md leading-relaxed text-muted">
          Возможно, страницу переместили или в адресе опечатка. Вернитесь на главную или
          посмотрите номера отеля.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          <Link href="/" className={buttonClass("primary", "lg")}>
            На главную
          </Link>
          <Link href="/nomera" className={buttonClass("outline", "lg")}>
            Смотреть номера
          </Link>
        </div>
      </div>
    </div>
  );
}
