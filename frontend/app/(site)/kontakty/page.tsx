import type { Metadata } from "next";

import { JsonLd } from "@/components/JsonLd";
import { PageHeader } from "@/components/ui/Prose";
import { Location } from "@/components/sections/Location";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import {BeSearchForm} from "@/components/be-forms/BeSearchForm";

export const metadata: Metadata = pageMetadata({
  title: "Контакты отеля Airis Residence в Алматы",
  description:
    "Алматы, ул. Наурызбай батыра 134/2. Телефон +7 (777) 531-00-09, почта airisresidence.kz@gmail.com. Стойка регистрации работает круглосуточно.",
  path: "/kontakty",
});

export default function ContactsPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "Контакты", path: "/kontakty" },
        ])}
      />

      <div className="pt-[calc(var(--header-h)+3rem)]">
        <div className="container-page">
          <div className="mb-10">
              <BeSearchForm />
          </div>

          <PageHeader
            eyebrow="Контакты"
            title="Как нас найти"
            description="Отель находится в Алмалинском районе Алматы. Стойка регистрации работает круглосуточно — звоните в любое время."
          />
        </div>
        <Location />
      </div>
    </>
  );
}
