import { notFound, redirect } from "next/navigation";

import { PrintButton } from "@/components/admin/PrintButton";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import { site } from "@/lib/site";
import type { AdminCompany, AdminCorpBooking } from "@/lib/adminTypes";

/**
 * Счёт на оплату — печатный документ, а не письмо.
 *
 * У нас нет ни своей бухгалтерской программы, ни отправки писем компаниям:
 * это было бы отдельной большой темой (шаблоны, доставляемость, а часто
 * компании и вовсе просят счёт по форме их 1С). Вместо этого — то, что
 * реально нужно менеджеру за один клик: готовый документ с реквизитами
 * обеих сторон и суммой, который остаётся сохранить как PDF и отправить
 * тем же способом, каким обычно переписываются с этой компанией.
 *
 * Реквизиты отеля берутся из site.ts, а не вводятся здесь заново — это тот
 * же источник, что и в подвале сайта и в договорах. Разъедутся один раз —
 * IIK в счёте больше не совпадёт с тем, что в реальности у банка.
 */

const money = new Intl.NumberFormat("ru-RU");

function formatDate(value: string): string {
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}

async function read<T>(path: string, fallback: T): Promise<T> {
  const res = await adminFetch(path).catch(() => null);
  if (!res || !res.ok) return fallback;
  return (await res.json()) as T;
}

export default async function InvoicePage(
  props: PageProps<"/admin/kompanii/[slug]/schet/[bookingId]">,
) {
  const { slug, bookingId } = await props.params;

  const [signedIn, companies, bookings] = await Promise.all([
    isAdminSignedIn(),
    read<AdminCompany[]>("/api/admin/corp/companies", []),
    read<AdminCorpBooking[]>(`/api/admin/corp/bookings?company=${slug}`, []),
  ]);
  if (!signedIn) redirect("/admin/login");

  const company = companies.find((item) => item.slug === slug);
  const booking = bookings.find((item) => String(item.id) === bookingId);
  if (!company || !booking) notFound();

  const issued = new Date().toLocaleDateString("ru-RU");

  return (
    <div>
      {/* Кнопка и подсказка не печатаются — @media print убирает их вместе
          с тёмной шапкой админки, чтобы на бумаге остался только документ. */}
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted">
          Это предпросмотр. На печати останется только сам счёт — без меню и этой строки.
        </p>
        <PrintButton />
      </div>

      {/* Сам документ: белый лист поверх тёмной админки — так он не сливается
          с фоном и заранее выглядит как то, что уйдёт на бумагу. */}
      <div
        id="invoice"
        className="mx-auto max-w-3xl rounded-2xl bg-white p-10 text-ink-950 shadow-2xl print:m-0 print:max-w-none print:rounded-none print:shadow-none"
      >
        <div className="flex items-start justify-between gap-6 border-b border-ink-950/15 pb-6">
          <div>
            <h1 className="font-display text-2xl">Счёт на оплату</h1>
            <p className="mt-1 text-sm text-ink-700/70">
              № {booking.invoiceNumber || booking.number} от {issued}
            </p>
          </div>
          <div className="text-right text-sm text-ink-700/70">
            <div className="font-display text-lg text-ink-950">{site.name}</div>
            <div>{site.legalName}</div>
          </div>
        </div>

        <div className="mt-6 grid gap-6 text-sm sm:grid-cols-2">
          <div>
            <div className="text-xs tracking-wide text-ink-700/50 uppercase">Исполнитель</div>
            <div className="mt-2 leading-relaxed">
              {site.legalName}
              <br />
              БИН {site.legal.bin}
              <br />
              ИИК {site.legal.iik}
              <br />
              БИК {site.legal.bik}, КБЕ {site.legal.kbe}
              <br />
              {site.legal.bank}
            </div>
          </div>
          <div>
            <div className="text-xs tracking-wide text-ink-700/50 uppercase">Заказчик</div>
            <div className="mt-2 leading-relaxed">
              {company.name}
              <br />
              {company.bin && (
                <>
                  БИН {company.bin}
                  <br />
                </>
              )}
              {company.contractNumber && (
                <>
                  Договор № {company.contractNumber}
                  {company.contractDate ? ` от ${formatDate(company.contractDate)}` : ""}
                  <br />
                </>
              )}
              {company.paymentTerms && <>Условия оплаты: {company.paymentTerms}</>}
            </div>
          </div>
        </div>

        <table className="mt-8 w-full text-sm">
          <thead>
            <tr className="border-b border-ink-950/15 text-left text-xs tracking-wide text-ink-700/50 uppercase">
              <th className="pb-2 font-normal">Услуга</th>
              <th className="pb-2 text-right font-normal">Ночей</th>
              <th className="pb-2 text-right font-normal">Номеров</th>
              <th className="pb-2 text-right font-normal">Цена/ночь</th>
              <th className="pb-2 text-right font-normal">Сумма</th>
            </tr>
          </thead>
          <tbody>
            {booking.items.map((item) => (
              <tr key={item.roomSlug} className="border-b border-ink-950/8">
                <td className="py-2.5">
                  Проживание, {item.roomName}
                  <div className="text-xs text-ink-700/60">
                    {formatDate(booking.checkIn)} — {formatDate(booking.checkOut)}
                    {booking.mealPlan === "none" ? " · без завтрака" : ""}
                  </div>
                </td>
                <td className="py-2.5 text-right tabular-nums">{booking.nights}</td>
                <td className="py-2.5 text-right tabular-nums">{item.roomsCount}</td>
                <td className="py-2.5 text-right tabular-nums">{money.format(item.pricePerNight)}</td>
                <td className="py-2.5 text-right tabular-nums">{money.format(item.amount)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={4} className="pt-4 text-right font-display text-base">
                Итого к оплате
              </td>
              <td className="pt-4 text-right font-display text-xl tabular-nums">
                {money.format(booking.totalAmount)} ₸
              </td>
            </tr>
          </tfoot>
        </table>

        {booking.guestName && (
          <p className="mt-6 text-sm text-ink-700/70">Гость: {booking.guestName}</p>
        )}

        <p className="mt-10 text-xs leading-relaxed text-ink-700/50">
          Счёт действителен для оплаты в срок, указанный в условиях договора. Оплата
          подтверждает согласие с условиями бронирования и отмены Airis Residence.
        </p>
      </div>

      {/* Печать: убираем всё, что не документ, и не даём браузеру обрезать
          страницу по своим полям вкривь — фон белый, тень и рамка не нужны. */}
      <style>{`
        @media print {
          .no-print { display: none !important; }
          header { display: none !important; }
          body { background: white !important; }
        }
      `}</style>
    </div>
  );
}
