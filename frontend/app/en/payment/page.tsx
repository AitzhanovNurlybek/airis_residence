import type { Metadata } from "next";
import Link from "next/link";

import { JsonLd } from "@/components/JsonLd";
import { PageHeader, Prose } from "@/components/ui/Prose";
import { buttonClass } from "@/components/ui/Button";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { site } from "@/lib/site";
import { siteEn } from "@/lib/en";

export const metadata: Metadata = pageMetadata({
  title: "Payment and cancellation — Airis Residence, Almaty",
  description:
    "How to pay at Airis Residence: online by card when booking (foreign cards accepted), cash, Visa or Mastercard at the front desk. Free cancellation up to 24 hours before arrival.",
  path: "/en/payment",
});

/**
 * Оплата по-английски. Реквизиты для юрлиц здесь не повторяются: счёт
 * иностранной компании выставляют по запросу, а казахстанские реквизиты
 * без контекста только путают туриста. Они — на русской странице.
 */
export default function PaymentPageEn() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", path: "/en" },
          { name: "Payment", path: "/en/payment" },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+3rem)] pb-8">
        <PageHeader
          eyebrow="Payment"
          title="Payment and cancellation"
          description="Pay online by card when you book, or at the front desk in cash or by card."
        />

        <Prose className="mt-12">
          <h2>Ways to pay</h2>
          <ul>
            <li>
              <strong>Online by card</strong> — right in the booking form on this website. {siteEn.policy.onlinePayment.split(". ")[1]}.
            </li>
            <li>
              <strong>By card at the front desk</strong> — Visa and Mastercard.
            </li>
            <li>
              <strong>In cash</strong> — at the front desk on arrival. The local currency is the tenge (₸).
            </li>
            <li>
              <strong>Bank transfer</strong> — for companies, by contract and invoice. Write to{" "}
              <a href={`mailto:${site.contacts.email}`}>{site.contacts.email}</a>.
            </li>
          </ul>

          <h2>Cancellation</h2>
          <p>{siteEn.policy.cancellation}.</p>

          <h2>Refunds</h2>
          <p>
            {siteEn.policy.refund}. If the money hasn&apos;t arrived after seven business days, write to us
            with your booking number and the last four digits of the card.
          </p>

          <h2>Other conditions</h2>
          <ul>
            <li>
              Check-in from {site.policy.checkIn}, check-out until {site.policy.checkOut}. {siteEn.policy.earlyCheckIn}.
            </li>
            <li>{siteEn.policy.children}. A baby cot for children under 2 is free on request.</li>
            <li>Pets are not allowed. Smoking is not allowed in the rooms.</li>
          </ul>
          <p>
            The full terms are set out in the <Link href="/oferta">public offer</Link> (in Russian).
          </p>
        </Prose>

        <div className="mt-12 flex flex-wrap gap-3">
          <Link href="/en/booking" className={buttonClass("primary", "lg")}>
            Book a room
          </Link>
          <Link href="/en/contacts" className={buttonClass("outline", "lg")}>
            Contact the hotel
          </Link>
        </div>
      </div>
    </>
  );
}
