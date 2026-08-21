"use client";

import Link from "next/link";
import { useState } from "react";

import { AdminButton, Field, inputClass, useToast } from "@/components/admin/ui";
import { AdminError, adminSend } from "@/lib/adminClient";
import type { AdminCompany } from "@/lib/adminTypes";

/**
 * Список корпоративных клиентов и заведение новых.
 *
 * Самостоятельной регистрации у компаний нет: корпоративный тариф — это
 * подписанный договор, а договор подписывает человек. Поэтому единственный
 * путь в кабинет начинается здесь.
 */

/** Код компании из названия: «ТОО «Альфа Строй»» → «alfa-stroy». */
function slugify(name: string): string {
  const map: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z",
    и: "i", й: "y", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r",
    с: "s", т: "t", у: "u", ф: "f", х: "h", ц: "c", ч: "ch", ш: "sh", щ: "sch",
    ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
    ә: "a", ғ: "g", қ: "q", ң: "n", ө: "o", ұ: "u", ү: "u", һ: "h", і: "i",
  };
  return name
    .toLowerCase()
    .replace(/[а-яёәғқңөұүһі]/g, (ch) => map[ch] ?? "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 58);
}

export function CompaniesBoard({ initial }: { initial: AdminCompany[] }) {
  const [companies, setCompanies] = useState(initial);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const toast = useToast();

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const created = await adminSend<AdminCompany>("/corp/companies", "POST", {
        slug: slug || slugify(name),
        name: name.trim(),
        bin: String(form.get("bin") ?? "").trim(),
        contractNumber: String(form.get("contractNumber") ?? "").trim(),
        contractDate: String(form.get("contractDate") ?? "") || null,
        paymentTerms: String(form.get("paymentTerms") ?? "").trim(),
        managerName: String(form.get("managerName") ?? "").trim(),
        managerEmail: String(form.get("managerEmail") ?? "").trim(),
        managerPhone: String(form.get("managerPhone") ?? "").trim(),
        discountPercent: Number(form.get("discountPercent") ?? 0) || 0,
      });
      setCompanies((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setAdding(false);
      setName("");
      setSlug("");
      setSlugTouched(false);
      toast.show("Компания создана. Теперь заведите ей сотрудников и прайс.");
    } catch (e) {
      toast.show(e instanceof AdminError ? e.message : "Не удалось создать", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-display text-3xl text-cream md:text-4xl">Корпоративные клиенты</h1>
        {!adding && (
          <AdminButton onClick={() => setAdding(true)}>+ Новая компания</AdminButton>
        )}
      </div>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
        Компания видит свои цены и оформляет заявки в кабинете на{" "}
        <code className="text-sand-300">/corp</code>. Доступ выдаёте вы: сама компания
        зарегистрироваться не может.
      </p>

      {adding && (
        <form
          onSubmit={create}
          className="mt-8 rounded-3xl border border-white/10 bg-ink-900/60 p-6 md:p-7"
        >
          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Название">
              <input
                required
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (!slugTouched) setSlug(slugify(e.target.value));
                }}
                placeholder="ТОО «Компания-пример А»"
                className={inputClass}
              />
            </Field>
            <Field
              label="Код"
              hint="Латиницей. Виден в адресах и в номерах счетов, потом не меняется."
            >
              <input
                required
                value={slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setSlug(e.target.value);
                }}
                pattern="[a-z0-9][a-z0-9\-]{1,58}"
                className={inputClass}
              />
            </Field>
            <Field label="БИН">
              <input name="bin" maxLength={12} className={inputClass} />
            </Field>
            <Field label="Скидка от прайса, %" hint="0 — если цены задаются по каждому номеру.">
              <input
                name="discountPercent"
                type="number"
                min={0}
                max={90}
                defaultValue={0}
                className={inputClass}
              />
            </Field>
            <Field label="Номер договора">
              <input name="contractNumber" className={inputClass} />
            </Field>
            <Field label="Дата договора">
              <input name="contractDate" type="date" className={inputClass} />
            </Field>
            <Field label="Условия оплаты" className="md:col-span-2">
              <input
                name="paymentTerms"
                placeholder="постоплата, 30 дн. (после услуг)"
                className={inputClass}
              />
            </Field>
            <Field label="Менеджер Airis">
              <input name="managerName" className={inputClass} />
            </Field>
            <Field label="Почта менеджера">
              <input name="managerEmail" type="email" className={inputClass} />
            </Field>
            <Field label="Телефон менеджера" className="md:col-span-2">
              <input name="managerPhone" type="tel" className={inputClass} />
            </Field>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <AdminButton type="submit" disabled={busy}>
              Создать
            </AdminButton>
            <AdminButton type="button" variant="secondary" onClick={() => setAdding(false)}>
              Отмена
            </AdminButton>
          </div>
        </form>
      )}

      {companies.length === 0 ? (
        <p className="mt-10 rounded-3xl border border-white/10 bg-ink-900/40 p-10 text-center text-muted">
          Компаний пока нет.
        </p>
      ) : (
        <div className="mt-8 grid gap-3">
          {companies.map((company) => (
            <Link
              key={company.slug}
              href={`/admin/kompanii/${company.slug}`}
              className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-ink-900/50 px-5 py-4 transition-colors hover:border-sand-400/40"
            >
              <div className="min-w-0">
                <div className="truncate text-[0.98rem] text-cream">{company.name}</div>
                <div className="mt-1 text-xs text-muted">
                  {company.bin ? `БИН ${company.bin}` : "БИН не указан"}
                  {company.contractNumber ? ` · договор ${company.contractNumber}` : ""}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3 text-xs">
                {company.discountPercent > 0 && (
                  <span className="rounded-full border border-white/15 px-3 py-1 text-cream/80">
                    −{company.discountPercent}%
                  </span>
                )}
                <span
                  className={`rounded-full border px-3 py-1 ${
                    company.isActive
                      ? "border-emerald-400/50 text-emerald-200"
                      : "border-wine-400/50 text-wine-200"
                  }`}
                >
                  {company.isActive ? "Активна" : "Приостановлена"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
