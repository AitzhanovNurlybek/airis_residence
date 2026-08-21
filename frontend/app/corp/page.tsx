import Link from "next/link";
import { redirect } from "next/navigation";

import { CorpHeader } from "@/components/corp/CorpHeader";
import { formatDate, formatMoney, getDictionary } from "@/lib/corp/dictionary";
import { getCorpLocale, getCorpMe } from "@/lib/corp/server";

/** Поле карточки компании: подпись сверху, значение под ней. */
function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-b border-ink-600/10 pb-2">
      <dt className="text-[0.65rem] tracking-[0.14em] text-ink-700/55 uppercase">{label}</dt>
      <dd className="mt-1 text-[0.95rem] break-words text-ink-950">{value || "—"}</dd>
    </div>
  );
}

function Counter({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-2xl bg-white px-6 py-5 shadow-sm">
      <div className="font-display text-3xl leading-none font-semibold text-wine-500">{value}</div>
      <div className="mt-2 text-xs text-ink-700/60">{label}</div>
    </div>
  );
}

function Tile({ href, title, hint }: { href: string; title: string; hint: string }) {
  return (
    <Link
      href={href}
      className="rounded-2xl bg-white px-6 py-5 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="font-display text-lg text-wine-500">{title}</div>
      <div className="mt-1 text-xs text-ink-700/60">{hint}</div>
    </Link>
  );
}

export default async function CorpCabinetPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const me = await getCorpMe();
  if (!me) redirect("/corp/login");

  const { company, user } = me;
  const contract = [
    company.contractNumber,
    company.contractDate ? formatDate(company.contractDate, locale) : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const isBoss = user.role === "admin";

  return (
    <>
      <CorpHeader
        dict={dict}
        locale={locale}
        companyName={company.name}
        userName={user.fullName || user.email}
      />

      <main className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <h1 className="font-display text-[clamp(1.9rem,4vw,2.8rem)] leading-tight font-semibold">
          {dict.cabinet.title}
        </h1>
        <Link
          href="/corp/password"
          className="mt-3 inline-block text-sm text-wine-600 underline underline-offset-4"
        >
          {dict.cabinet.changePassword}
        </Link>

        <p className="mt-5 max-w-3xl rounded-xl border-l-2 border-wine-500 bg-white/70 px-4 py-3 text-sm leading-relaxed text-ink-700/85">
          {dict.notice}
        </p>

        <section className="mt-8 rounded-3xl bg-white p-6 shadow-sm md:p-8">
          <h2 className="font-display text-2xl font-semibold">{company.name}</h2>
          <dl className="mt-6 grid gap-x-10 gap-y-5 md:grid-cols-2">
            <Field label={dict.cabinet.bin} value={company.bin} />
            <Field
              label={dict.cabinet.manager}
              value={[company.managerName, company.managerEmail].filter(Boolean).join(" · ")}
            />
            <Field label={dict.cabinet.contract} value={contract} />
            <Field label={dict.cabinet.phone} value={company.managerPhone} />
            <Field label={dict.cabinet.payment} value={company.paymentTerms} />
            <Field label={dict.cabinet.email} value={user.email} />
          </dl>
        </section>

        <section className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 md:max-w-2xl">
          <Counter value={String(me.activeBookings)} label={dict.cabinet.activeBookings} />
          <Counter value={formatMoney(me.totalAmount)} label={dict.cabinet.totalAmount} />
          <Counter value={formatMoney(me.paidAmount)} label={dict.cabinet.paidAmount} />
        </section>

        {/* Плитка появляется вместе со своей страницей: ссылка в никуда хуже
            её отсутствия. Финансы и отчёты — следующий заход. */}
        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Tile
            href="/corp/booking"
            title={dict.cabinet.tiles.book}
            hint={dict.cabinet.tiles.bookHint}
          />
          <Tile
            href="/corp/bookings"
            title={dict.cabinet.tiles.bookings}
            hint={dict.cabinet.tiles.bookingsHint}
          />
          {isBoss && (
            <Tile
              href="/corp/employees"
              title={dict.cabinet.tiles.employees}
              hint={dict.cabinet.tiles.employeesHint}
            />
          )}
        </section>
      </main>
    </>
  );
}
