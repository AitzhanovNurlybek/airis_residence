import Link from "next/link";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { PasswordForm } from "@/components/corp/PasswordForm";
import { getDictionary } from "@/lib/corp/dictionary";
import { getCorpLocale, getCorpMe } from "@/lib/corp/server";

export default async function CorpPasswordPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const me = await getCorpMe();
  if (!me) redirect("/corp/login");

  return (
    <>
      <CorpHeader
        dict={dict}
        locale={locale}
        companyName={me.company.name}
        userName={me.user.fullName || me.user.email}
        isAdmin={me.user.role === "admin"}
      />

      <main className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <Link href="/corp" prefetch={false} className="text-sm text-wine-600 underline underline-offset-4">
          ← {dict.nav.back}
        </Link>

        <h1 className="mt-5 font-display text-[clamp(1.9rem,4vw,2.8rem)] leading-tight font-semibold">
          {dict.password.title}
        </h1>

        <PasswordForm t={dict.password} />
      </main>
    </>
  );
}
