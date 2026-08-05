import type { Metadata } from "next";

import { JsonLd } from "@/components/JsonLd";
import { PageHeader } from "@/components/ui/Prose";
import { Location } from "@/components/sections/Location";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Контакты отеля Airis Residence в Алматы",
  description:
    "Адрес: Алматы, ул. Наурызбай батыра 134/2. Телефоны +7 (777) 531-00-09 и +7 (727) 277-20-20, почта airisresidence.kz@gmail.com. Стойка регистрации работает круглосуточно.",
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
