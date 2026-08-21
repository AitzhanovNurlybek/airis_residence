import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { LoginForm } from "@/components/corp/LoginForm";
import { getDictionary } from "@/lib/corp/dictionary";
import { getCorpLocale, getCorpMe } from "@/lib/corp/server";

export default async function CorpLoginPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  // Уже вошёл — форма ему не нужна.
  if (await getCorpMe()) redirect("/corp");

  return (
    <>
      <CorpHeader dict={dict} locale={locale} signedIn={false} />
      <main className="grid min-h-[calc(100dvh-4rem)] place-items-center px-5 py-14">
        <div className="w-full max-w-md">
          <h1 className="text-center font-display text-[clamp(1.8rem,4vw,2.6rem)] leading-tight font-semibold text-ink-950">
            {dict.login.title}
          </h1>
          <p className="mt-3 text-center text-sm text-ink-700/70">{dict.login.subtitle}</p>
          <div className="mt-8 flex justify-center">
            <LoginForm t={{ ...dict.login, loading: dict.common.loading }} />
          </div>
        </div>
      </main>
    </>
  );
}
