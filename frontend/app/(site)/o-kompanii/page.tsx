import type { Metadata } from "next";
import Link from "next/link";

import { JsonLd } from "@/components/JsonLd";
import { PageHeader, Prose } from "@/components/ui/Prose";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { site, formatPrice } from "@/lib/site";
import { getRooms } from "@/lib/rooms";
import { buttonClass } from "@/components/ui/Button";

export const metadata: Metadata = pageMetadata({
  title: "О компании — ТОО INCOME HOUSE, отель Airis Residence",
  description:
    `Airis Residence — городской отель на ${site.roomsCount} номеров в центре Алматы под управлением ТОО INCOME HOUSE. Реквизиты, контакты и информация о компании.`,
  path: "/o-kompanii",
});

export default async function AboutCompanyPage() {
  const rooms = await getRooms();

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "О компании", path: "/o-kompanii" },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+3rem)] pb-8">
        <PageHeader
          eyebrow="О компании"
          title="Airis Residence"
          description={`Городской отель на ${site.roomsCount} номеров в центре Алматы под управлением ${site.legalName}.`}
        />

        <Prose className="mt-12">
          <h2>Об отеле</h2>
          <p>
            Airis Residence — небольшой отель в Алмалинском районе Алматы, на улице Наурызбай
            батыра 134/2. Мы работаем в формате городского отеля: {site.roomsCount} номеров
            пяти категорий, круглосуточная стойка регистрации, включённый завтрак и
            расположение в пешей доступности от делового и культурного центра города.
          </p>
          <p>
            Отель ориентирован на деловые поездки и короткие городские визиты. Заезд
            с {site.policy.checkIn}, выезд до {site.policy.checkOut}. Стойка регистрации
            работает без перерывов, поэтому встретим и ночью. Ранний заезд или поздний
            выезд — платная услуга, {formatPrice(site.policy.earlyCheckInFee)}, при наличии
            свободных номеров.
          </p>

          <h2>Категории номеров</h2>
          <ul>
            {rooms.map((room) => (
              <li key={room.slug}>
                <Link href={`/nomera/${room.slug}`}>{room.shortName}</Link> — {room.area}, до{" "}
                {room.capacity} гостей, от {formatPrice(room.price)} за ночь.
              </li>
            ))}
          </ul>

          <h2>Реквизиты компании</h2>
          <table>
            <tbody>
              <tr>
                <th>Полное наименование</th>
                <td>{site.legalName}</td>
              </tr>
              <tr>
                <th>БИН</th>
                <td>{site.legal.bin}</td>
              </tr>
              <tr>
                <th>Юридический адрес</th>
                <td>{site.address.full}</td>
              </tr>
              <tr>
                <th>ИИК</th>
                <td>{site.legal.iik}</td>
              </tr>
              <tr>
                <th>БИК</th>
                <td>{site.legal.bik}</td>
              </tr>
              <tr>
                <th>Банк</th>
                <td>{site.legal.bank}</td>
              </tr>
              <tr>
                <th>КБе</th>
                <td>{site.legal.kbe}</td>
              </tr>
            </tbody>
          </table>

          <h2>Контакты</h2>
          <ul>
            <li>
              Телефон: <a href={`tel:${site.contacts.phonePrimaryRaw}`}>{site.contacts.phonePrimary}</a>
            </li>
            <li>
              Городской: <a href={`tel:${site.contacts.phoneCityRaw}`}>{site.contacts.phoneCity}</a>
            </li>
            <li>
              Почта: <a href={`mailto:${site.contacts.email}`}>{site.contacts.email}</a>
            </li>
            <li>Режим работы: {site.contacts.hours}</li>
          </ul>
        </Prose>

        <div className="mt-12">
          <Link href="/kontakty" className={buttonClass("outline", "lg")}>
            Карта и схема проезда
          </Link>
        </div>
      </div>
    </>
  );
}
