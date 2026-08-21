import Image from "next/image";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { LoginForm } from "@/components/corp/LoginForm";
import { Logo } from "@/components/ui/Logo";
import { getDictionary } from "@/lib/corp/dictionary";
import { getCorpLocale, getCorpMe } from "@/lib/corp/server";

/**
 * Вход в корпоративный раздел.
 *
 * Единственная страница кабинета на тёмном фоне: человек попадает сюда прямо
 * с сайта отеля, и снимок лобби связывает закрытый раздел с ним. Дальше, где
 * читают таблицы и суммы, фон светлый — на фотографии цифры не читаются.
 *
 * Фон прижат к самой странице, а не к лейауту: остальные экраны кабинета
 * рабочие, и общий тёмный фон под таблицами был бы им во вред.
 */
export default async function CorpLoginPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  // Уже вошёл — форма ему не нужна.
  if (await getCorpMe()) redirect("/corp");

  return (
    <div className="relative min-h-dvh">
      {/* Без отрицательного z-index: лейаут кабинета залит непрозрачным
          bg-sand-100, и -z-10 увёл бы снимок ЗА эту заливку — фон просто
          не появлялся. Слои разложены порядком в разметке. */}
      <div className="absolute inset-0 overflow-hidden">
        <Image
          src="/images/hotel/lobby.jpg"
          alt=""
          aria-hidden
          fill
          priority
          sizes="100vw"
          className="object-cover"
        />
        {/* Затемнение обязательно: поверх снимка идёт белая карточка формы и
            светлый текст, а лобби снято при тёплом свете — без него ни то, ни
            другое не читается. */}
        <div className="absolute inset-0 bg-ink-950/70" />
      </div>

      <div className="relative">
        <CorpHeader dict={dict} locale={locale} signedIn={false} />

        <main className="grid min-h-[calc(100dvh-4rem)] place-items-center px-5 py-12">
          <div className="w-full max-w-lg rounded-[2rem] border border-white/25 px-5 py-10 sm:px-10">
            <Logo className="mx-auto h-9 w-auto" />

            <h1 className="mt-8 text-center font-display text-[clamp(1.7rem,4vw,2.4rem)] leading-[1.15] font-semibold text-cream">
              {dict.login.title}
            </h1>
            <p className="mt-3 text-center text-sm leading-relaxed text-cream/65">
              {dict.login.subtitle}
            </p>

            <div className="mt-8 flex justify-center">
              <LoginForm t={{ ...dict.login, loading: dict.common.loading }} />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
