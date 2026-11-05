import type { Metadata } from "next";

import { JsonLd } from "@/components/JsonLd";
import { PageHeader } from "@/components/ui/Prose";
import { Location } from "@/components/sections/Location";
import { BeSearchForm } from "@/components/be-forms/BeSearchForm";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { site } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "Contacts — Airis Residence hotel, Almaty",
  description: `134/2 Nauryzbai Batyr St., Almaty. Phone ${site.contacts.phonePrimary}, email ${site.contacts.email}, WhatsApp in English. The front desk is open 24/7.`,
  path: "/en/contacts",
});

export default function ContactsPageEn() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", path: "/en" },
          { name: "Contacts", path: "/en/contacts" },
        ])}
      />

      <div className="pt-[calc(var(--header-h)+3rem)]">
        <div className="container-page">
          <div className="mb-10">
            <BeSearchForm />
          </div>

          <PageHeader
            eyebrow="Contacts"
            title="How to find us"
            description="The hotel is in Almaty's Almaly district. The front desk is open around the clock — call or message us on WhatsApp any time, in English."
          />
        </div>
        <Location lang="en" />
      </div>
    </>
  );
}
