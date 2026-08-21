import Link from "next/link";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { EmployeeManager } from "@/components/corp/EmployeeManager";
import { getDictionary } from "@/lib/corp/dictionary";
import { getCorpEmployees, getCorpLocale, getCorpMe } from "@/lib/corp/server";

export default async function CorpEmployeesPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const [me, employeesResult] = await Promise.all([getCorpMe(), getCorpEmployees()]);
  if (!me) redirect("/corp/login");
  // Раздел для ответственного. Бэкенд отказал бы и так, но лучше увести
  // человека в кабинет, чем показать ему пустой экран с ошибкой.
  if (me.user.role !== "admin") redirect("/corp");

  const employees = employeesResult ?? [];

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
          {dict.employees.title}
        </h1>
        <p className="mt-2 text-sm text-ink-700/65">{dict.employees.subtitle}</p>

        <EmployeeManager
          employees={employees}
          meId={me.user.id}
          dict={dict}
          locale={locale}
        />
      </main>
    </>
  );
}
