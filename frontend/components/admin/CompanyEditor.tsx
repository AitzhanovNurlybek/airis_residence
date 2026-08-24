"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AdminButton, Field, inputClass, useToast } from "@/components/admin/ui";
import { AdminError, adminSend } from "@/lib/adminClient";
import {
  CORP_STATUSES,
  type AdminCompany,
  type AdminCompanyRate,
  type AdminCompanyUser,
  type AdminCorpBooking,
  type AdminRoom,
} from "@/lib/adminTypes";

/**
 * Карточка корпоративного клиента: реквизиты, прайс, сотрудники и заявки.
 *
 * Всё на одном экране намеренно. Менеджер открывает компанию, когда с ней
 * что-то происходит — позвонили, попросили счёт, добавился сотрудник, — и
 * гонять его по четырём вкладкам ради трёх полей смысла нет.
 */

const money = new Intl.NumberFormat("ru-RU");

const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function shortDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("ru-RU");
}

/** Та же формула, что на бэкенде: точная цена важнее процента, округление вниз до сотни. */
function effectivePrice(publicPrice: number, discount: number, override?: number): number {
  if (override != null && !Number.isNaN(override)) return override;
  if (discount > 0) return Math.floor((publicPrice * (100 - discount)) / 100 / 100) * 100;
  return publicPrice;
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="mt-8 rounded-3xl border border-white/10 bg-ink-900/50 p-6 md:p-7">
      <h2 className="font-display text-2xl text-cream">{title}</h2>
      {hint && <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">{hint}</p>}
      {children}
    </section>
  );
}

export function CompanyEditor({
  company: initialCompany,
  rooms,
  rates: initialRates,
  users: initialUsers,
  bookings: initialBookings,
}: {
  company: AdminCompany;
  rooms: AdminRoom[];
  rates: AdminCompanyRate[];
  users: AdminCompanyUser[];
  bookings: AdminCorpBooking[];
}) {
  const [company, setCompany] = useState(initialCompany);
  const [users, setUsers] = useState(initialUsers);
  const [bookings, setBookings] = useState(initialBookings);
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [addingUser, setAddingUser] = useState(false);
  const toast = useToast();

  // Пустая строка означает «цены по этому номеру нет, считай от процента».
  const [prices, setPrices] = useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    for (const room of rooms) {
      const found = initialRates.find((rate) => rate.roomSlug === room.slug);
      map[room.slug] = found ? String(found.price) : "";
    }
    return map;
  });

  function fail(e: unknown) {
    toast.show(e instanceof AdminError ? e.message : "Не удалось сохранить", "error");
  }

  async function saveRequisites(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const saved = await adminSend<AdminCompany>(`/corp/companies/${company.slug}`, "PATCH", {
        name: String(form.get("name") ?? "").trim(),
        bin: String(form.get("bin") ?? "").trim(),
        contractNumber: String(form.get("contractNumber") ?? "").trim(),
        contractDate: String(form.get("contractDate") ?? "") || null,
        paymentTerms: String(form.get("paymentTerms") ?? "").trim(),
        managerName: String(form.get("managerName") ?? "").trim(),
        managerEmail: String(form.get("managerEmail") ?? "").trim(),
        managerPhone: String(form.get("managerPhone") ?? "").trim(),
        discountPercent: Number(form.get("discountPercent") ?? 0) || 0,
        breakfastPrice: Number(form.get("breakfastPrice") ?? 0) || 0,
      });
      setCompany(saved);
      toast.show("Реквизиты сохранены");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function toggleCompany() {
    setBusy(true);
    try {
      const saved = await adminSend<AdminCompany>(`/corp/companies/${company.slug}`, "PATCH", {
        isActive: !company.isActive,
      });
      setCompany(saved);
      toast.show(saved.isActive ? "Доступ компании восстановлен" : "Доступ компании приостановлен");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function saveRates() {
    setBusy(true);
    try {
      // Отправляем прайс целиком: пустое поле означает «цены нет», и строка
      // должна исчезнуть, а не остаться от прошлого договора.
      const payload = Object.entries(prices)
        .filter(([, value]) => value.trim() !== "")
        .map(([roomSlug, value]) => ({ roomSlug, price: Number(value) }));
      if (payload.some((line) => Number.isNaN(line.price) || line.price < 0)) {
        toast.show("Цена должна быть числом", "error");
        return;
      }
      await adminSend<AdminCompanyRate[]>(`/corp/companies/${company.slug}/rates`, "PUT", payload);
      toast.show("Прайс сохранён");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function addUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    setBusy(true);
    try {
      const created = await adminSend<AdminCompanyUser>(
        `/corp/companies/${company.slug}/users`,
        "POST",
        {
          email: String(form.get("email") ?? "").trim(),
          fullName: String(form.get("fullName") ?? "").trim(),
          phone: String(form.get("phone") ?? "").trim(),
          role: String(form.get("role") ?? "employee"),
          password: String(form.get("password") ?? ""),
        },
      );
      setUsers((prev) => [...prev, created]);
      formEl.reset();
      setAddingUser(false);
      toast.show("Сотрудник заведён. Пароль передайте ему лично.");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function patchUser(id: number, body: Record<string, unknown>) {
    setBusy(true);
    try {
      const saved = await adminSend<AdminCompanyUser>(`/corp/users/${id}`, "PATCH", body);
      setUsers((prev) => prev.map((u) => (u.id === id ? saved : u)));
      toast.show("Сохранено");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function removeCompany() {
    // Первое подтверждение — от случайного клика. Название печатать не просим:
    // компаний немного, а лишний обряд раздражает и его начинают проматывать.
    if (!window.confirm(`Удалить компанию «${company.name}»? Это необратимо.`)) return;

    setBusy(true);
    try {
      await adminSend(`/corp/companies/${company.slug}`, "DELETE");
      router.push("/admin/kompanii");
      router.refresh();
      return;
    } catch (e) {
      // 409 значит «у компании есть история». Бэкенд присылает, сколько именно
      // записей исчезнет — показываем это человеку, а не своё общее слово.
      if (e instanceof AdminError && e.status === 409) {
        if (window.confirm(`${e.message}

Всё равно удалить?`)) {
          try {
            await adminSend(`/corp/companies/${company.slug}?force=true`, "DELETE");
            router.push("/admin/kompanii");
            router.refresh();
            return;
          } catch (inner) {
            fail(inner);
          }
        }
      } else {
        fail(e);
      }
    } finally {
      setBusy(false);
    }
  }

  async function setBookingStatus(booking: AdminCorpBooking, status: AdminCorpBooking["status"]) {
    // Счёт без номера — бумага без реквизита: бухгалтерия компании его не примет.
    let invoiceNumber = booking.invoiceNumber;
    if (status === "invoiced" && !invoiceNumber) {
      invoiceNumber = window.prompt("Номер счёта") ?? "";
      if (!invoiceNumber) return;
    }
    setBusy(true);
    try {
      const saved = await adminSend<AdminCorpBooking>(
        `/corp/bookings/${booking.id}/status`,
        "PATCH",
        { status, invoiceNumber, reason: "" },
      );
      setBookings((prev) => prev.map((b) => (b.id === booking.id ? saved : b)));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Link href="/admin/kompanii" className="text-sm text-sand-300 underline underline-offset-4">
        ← Все компании
      </Link>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-display text-3xl text-cream md:text-4xl">{company.name}</h1>
        <AdminButton
          variant={company.isActive ? "danger" : "secondary"}
          disabled={busy}
          onClick={toggleCompany}
        >
          {company.isActive ? "Приостановить доступ" : "Восстановить доступ"}
        </AdminButton>
      </div>
      {!company.isActive && (
        <p className="mt-3 rounded-xl border border-wine-400/40 bg-wine-900/25 px-4 py-3 text-sm text-wine-200">
          Доступ приостановлен: сотрудники компании в кабинет не войдут, а те, кто уже вошёл,
          получат отказ на следующем же действии.
        </p>
      )}

      {/* ─────────────── Реквизиты ─────────────── */}
      <Section title="Реквизиты и договор">
        <form onSubmit={saveRequisites} className="mt-5 grid gap-5 md:grid-cols-2">
          <Field label="Название">
            <input name="name" defaultValue={company.name} required className={inputClass} />
          </Field>
          <Field label="БИН">
            <input name="bin" defaultValue={company.bin} maxLength={12} className={inputClass} />
          </Field>
          <Field label="Номер договора">
            <input
              name="contractNumber"
              defaultValue={company.contractNumber}
              className={inputClass}
            />
          </Field>
          <Field label="Дата договора">
            <input
              name="contractDate"
              type="date"
              defaultValue={company.contractDate ?? ""}
              className={inputClass}
            />
          </Field>
          <Field label="Условия оплаты" className="md:col-span-2">
            <input
              name="paymentTerms"
              defaultValue={company.paymentTerms}
              placeholder="постоплата, 30 дн. (после услуг)"
              className={inputClass}
            />
          </Field>
          <Field label="Менеджер Airis">
            <input name="managerName" defaultValue={company.managerName} className={inputClass} />
          </Field>
          <Field label="Почта менеджера">
            <input
              name="managerEmail"
              type="email"
              defaultValue={company.managerEmail}
              className={inputClass}
            />
          </Field>
          <Field label="Телефон менеджера">
            <input
              name="managerPhone"
              type="tel"
              defaultValue={company.managerPhone}
              className={inputClass}
            />
          </Field>
          <Field
            label="Скидка от прайса, %"
            hint="Применяется к номерам без своей цены. Результат округляется вниз до сотни тенге."
          >
            <input
              name="discountPercent"
              type="number"
              min={0}
              max={90}
              defaultValue={company.discountPercent}
              className={inputClass}
            />
          </Field>
          <Field
            label="Вычет за отказ от завтрака, ₸"
            hint="На гостя за ночь. Завтрак входит в цену любого номера, поэтому это вычет, а не доплата. Ноль — цена та же, но выбор всё равно попадёт в заявку: кухне нужно знать число гостей на утро."
          >
            <input
              name="breakfastPrice"
              type="number"
              min={0}
              step={500}
              defaultValue={company.breakfastPrice}
              className={inputClass}
            />
          </Field>
          <div className="md:col-span-2">
            <AdminButton type="submit" disabled={busy}>
              Сохранить реквизиты
            </AdminButton>
          </div>
        </form>
      </Section>

      {/* ─────────────── Прайс ─────────────── */}
      <Section
        title="Корпоративный прайс"
        hint="Цена по договору важнее процента скидки. Пустое поле — цены нет, считается от процента."
      >
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs text-muted uppercase">
                <th className="py-3 pr-4 font-normal">Номер</th>
                <th className="py-3 pr-4 text-right font-normal">На сайте</th>
                <th className="py-3 pr-4 text-right font-normal">Цена по договору</th>
                <th className="py-3 text-right font-normal">Компания увидит</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((room) => {
                const raw = prices[room.slug] ?? "";
                const override = raw.trim() === "" ? undefined : Number(raw);
                const shown = effectivePrice(room.price, company.discountPercent, override);
                return (
                  <tr key={room.slug} className="border-b border-white/6 last:border-0">
                    <td className="py-3 pr-4 text-cream">{room.shortName}</td>
                    <td className="py-3 pr-4 text-right text-muted">{money.format(room.price)}</td>
                    <td className="py-3 pr-4 text-right">
                      <input
                        value={raw}
                        onChange={(e) =>
                          setPrices((prev) => ({ ...prev, [room.slug]: e.target.value }))
                        }
                        inputMode="numeric"
                        placeholder="—"
                        className={`${inputClass} w-32 text-right`}
                      />
                    </td>
                    <td className="py-3 text-right text-sand-200">{money.format(shown)} ₸</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <AdminButton className="mt-5" disabled={busy} onClick={saveRates}>
          Сохранить прайс
        </AdminButton>
      </Section>

      {/* ─────────────── Сотрудники ─────────────── */}
      <Section
        title="Сотрудники"
        hint="Пароль задаёте вы и передаёте человеку сами: писем кабинет не рассылает."
      >
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[42rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs text-muted uppercase">
                <th className="py-3 pr-4 font-normal">Имя</th>
                <th className="py-3 pr-4 font-normal">Почта</th>
                <th className="py-3 pr-4 font-normal">Роль</th>
                <th className="py-3 pr-4 font-normal">Вход</th>
                <th className="py-3 font-normal" />
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-muted">
                    Сотрудников нет — в кабинет войти некому.
                  </td>
                </tr>
              )}
              {users.map((person) => (
                <tr key={person.id} className="border-b border-white/6 last:border-0">
                  <td className="py-3 pr-4 text-cream">
                    {person.fullName || "—"}
                    {!person.isActive && (
                      <span className="mt-1 block text-xs text-muted">отключён</span>
                    )}
                    {person.isActive && !person.hasPassword && (
                      <span className="mt-1 block text-xs text-wine-200">
                        пароль не задан — войти не может
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-muted">{person.email}</td>
                  <td className="py-3 pr-4">
                    <select
                      value={person.role}
                      disabled={busy}
                      onChange={(e) => patchUser(person.id, { role: e.target.value })}
                      className="rounded-lg border border-white/12 bg-ink-950/60 px-2 py-1.5 text-sm text-cream"
                    >
                      <option value="admin">Ответственный</option>
                      <option value="employee">Сотрудник</option>
                    </select>
                  </td>
                  <td className="py-3 pr-4 text-muted">
                    {person.lastLoginAt ? dateTime.format(new Date(person.lastLoginAt)) : "ни разу"}
                  </td>
                  <td className="py-3 text-right whitespace-nowrap">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        const next = window.prompt("Новый пароль (минимум 8 символов)");
                        if (!next) return;
                        if (next.length < 8) {
                          toast.show("Пароль короче 8 символов", "error");
                          return;
                        }
                        patchUser(person.id, { password: next });
                      }}
                      className="text-xs text-sand-300 underline underline-offset-2 disabled:opacity-50"
                    >
                      Задать пароль
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => patchUser(person.id, { isActive: !person.isActive })}
                      className="ml-4 text-xs text-muted underline underline-offset-2 disabled:opacity-50"
                    >
                      {person.isActive ? "Отключить" : "Включить"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {addingUser ? (
          <form onSubmit={addUser} className="mt-6 grid gap-5 md:grid-cols-2">
            <Field label="Рабочая почта">
              <input name="email" type="email" required className={inputClass} />
            </Field>
            <Field label="Имя и фамилия">
              <input name="fullName" className={inputClass} />
            </Field>
            <Field label="Телефон">
              <input name="phone" type="tel" className={inputClass} />
            </Field>
            <Field label="Роль" hint="Ответственный заводит коллег и видит все брони компании.">
              <select name="role" defaultValue="employee" className={inputClass}>
                <option value="employee">Сотрудник</option>
                <option value="admin">Ответственный</option>
              </select>
            </Field>
            <Field label="Пароль" hint="Минимум 8 символов." className="md:col-span-2">
              <input name="password" type="text" minLength={8} required className={inputClass} />
            </Field>
            <div className="flex gap-3 md:col-span-2">
              <AdminButton type="submit" disabled={busy}>
                Завести
              </AdminButton>
              <AdminButton type="button" variant="secondary" onClick={() => setAddingUser(false)}>
                Отмена
              </AdminButton>
            </div>
          </form>
        ) : (
          <AdminButton className="mt-6" variant="secondary" onClick={() => setAddingUser(true)}>
            + Добавить сотрудника
          </AdminButton>
        )}
      </Section>

      {/* ─────────────── Заявки ─────────────── */}
      <Section
        title="Заявки компании"
        hint="Наличие номеров подтверждаете вы: система бронирования отеля пока не отдаёт его в кабинет."
      >
        {bookings.length === 0 ? (
          <p className="mt-5 text-muted">Заявок пока нет.</p>
        ) : (
          <div className="mt-5 grid gap-3">
            {bookings.map((booking) => {
              const tone =
                CORP_STATUSES.find((s) => s.value === booking.status)?.tone ?? "border-white/15";
              const label = CORP_STATUSES.find((s) => s.value === booking.status)?.label ?? booking.status;
              return (
                <article
                  key={booking.id}
                  className="rounded-2xl border border-white/10 bg-ink-950/40 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-cream">
                        {booking.number} · {shortDate(booking.checkIn)} — {shortDate(booking.checkOut)}
                        <span className="ml-2 text-xs text-muted">{booking.nights} ноч.</span>
                      </div>
                      <div className="mt-1 text-xs text-muted">
                        {booking.items.map((i) => `${i.roomName} × ${i.roomsCount}`).join(", ")}
                        {booking.guestName ? ` · гость: ${booking.guestName}` : ""}
                        {booking.createdByName ? ` · оформил: ${booking.createdByName}` : ""}
                        {/* Пишем только отказ. «Завтрак включён» — обычный
                            случай, и повторять его в каждой строке значит
                            заставить менеджера вычитывать шум ради
                            редкого исключения. */}
                        {booking.mealPlan === "none" ? " · без завтрака" : ""}
                      </div>
                      {booking.comment && (
                        <div className="mt-2 text-sm text-cream/80">{booking.comment}</div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="font-display text-xl text-sand-200">
                        {money.format(booking.totalAmount)} ₸
                      </div>
                      <span className={`mt-2 inline-block rounded-full border px-3 py-1 text-xs ${tone}`}>
                        {label}
                      </span>
                      {booking.invoiceNumber && (
                        <div className="mt-1 text-xs text-muted">счёт {booking.invoiceNumber}</div>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Link
                      href={`/admin/kompanii/${company.slug}/schet/${booking.id}`}
                      target="_blank"
                      className="rounded-full border border-sand-400/40 px-3 py-1.5 text-xs text-sand-300 transition-colors hover:border-sand-400 hover:text-sand-200"
                    >
                      Счёт на печать ↗
                    </Link>
                    {CORP_STATUSES.filter((s) => s.value !== booking.status).map((s) => (
                      <button
                        key={s.value}
                        type="button"
                        disabled={busy}
                        onClick={() => setBookingStatus(booking, s.value)}
                        className="rounded-full border border-white/12 px-3 py-1.5 text-xs text-muted transition-colors hover:border-sand-400/50 hover:text-cream disabled:opacity-50"
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Section>

      {/* Опасная зона внизу и отдельным блоком: рядом с обычными действиями
          такая кнопка рано или поздно будет нажата не глядя. */}
      <section className="mt-8 rounded-3xl border border-wine-400/30 bg-wine-900/15 p-6 md:p-7">
        <h2 className="font-display text-2xl text-cream">Удалить компанию</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
          Вместе с компанией исчезнут её сотрудники, корпоративный прайс и вся история
          бронирований с номерами счетов. Восстановить будет нечем. Если компания просто
          перестала обслуживаться — приостановите доступ: кабинет закроется, а история
          останется.
        </p>
        <AdminButton variant="danger" className="mt-5" disabled={busy} onClick={removeCompany}>
          Удалить «{company.name}»
        </AdminButton>
      </section>
    </div>
  );
}
