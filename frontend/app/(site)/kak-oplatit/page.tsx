import type { Metadata } from "next";
import Link from "next/link";

import { JsonLd } from "@/components/JsonLd";
import { PageHeader, Prose } from "@/components/ui/Prose";
import { breadcrumbJsonLd, pageMetadata } from "@/lib/seo";
import { site } from "@/lib/site";
import { isOnlinePaymentLive } from "@/lib/booking";
import { buttonClass } from "@/components/ui/Button";
import {BeSearchForm} from "@/components/be-forms/BeSearchForm";

export const metadata: Metadata = pageMetadata({
  title: "Как оплатить проживание — отель Airis Residence, Алматы",
  description:
    "Способы оплаты в отеле Airis Residence: наличные, карты Visa и Mastercard, безналичный расчёт для юридических лиц. Реквизиты ТОО INCOME HOUSE.",
  path: "/kak-oplatit",
});

export default function PaymentPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Главная", path: "/" },
          { name: "Как оплатить", path: "/kak-oplatit" },
        ])}
      />

      <div className="container-page pt-[calc(var(--header-h)+3rem)] pb-8">
        <div className="mb-10">
          <BeSearchForm />
        </div>

        <PageHeader
          eyebrow="Оплата"
          title="Как оплатить проживание"
          description="Принимаем оплату наличными, банковской картой и по безналичному расчёту для юридических лиц."
        />

        <Prose className="mt-12">
          <h2>Способы оплаты</h2>
          <ul>
            <li>
              <strong>Наличными</strong> — на стойке регистрации при заселении.
            </li>
            <li>
              <strong>Банковской картой</strong> — Visa и Mastercard, оплата на стойке
              регистрации через терминал.
            </li>
            <li>
              <strong>Онлайн-оплата картой</strong> —{" "}
              {isOnlinePaymentLive
                ? "доступна при бронировании на сайте."
                : "подключается: сейчас бронь подтверждается менеджером, оплата на месте."}
            </li>
            <li>
              <strong>Безналичный расчёт</strong> — для юридических лиц по договору и счёту
              на оплату.
            </li>
          </ul>

          <h2>Оплата для юридических лиц</h2>
          <p>
            Работаем с компаниями по договору. Выставим счёт на оплату в день обращения и
            передадим полный комплект закрывающих документов: акт выполненных работ и
            счёт-фактуру.
          </p>
          <p>
            Для выставления счёта напишите на{" "}
            <a href={`mailto:${site.contacts.email}`}>{site.contacts.email}</a> или позвоните
            по номеру <a href={`tel:${site.contacts.phoneCityRaw}`}>{site.contacts.phoneCity}</a>.
            Укажите наименование компании, БИН, даты проживания, количество и тип номеров.
          </p>

          <h2>Реквизиты для оплаты</h2>
          <table>
            <tbody>
              <tr>
                <th>Наименование</th>
                <td>{site.legalName}</td>
              </tr>
              <tr>
                <th>БИН</th>
                <td>{site.legal.bin}</td>
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
              <tr>
                <th>Юридический адрес</th>
                <td>{site.address.full}</td>
              </tr>
            </tbody>
          </table>

          <h2>Возврат и отмена брони</h2>
          <p>
            Бесплатная отмена брони — не позднее чем за 24 часа до заезда. При более поздней
            отмене или незаезде удерживается стоимость первых суток проживания.
          </p>
          {/* Сроки подтверждены поддержкой платёжной системы 2026-08-31. Раньше
              здесь стояло «до 14 рабочих дней» — цифра взята при разработке
              наугад и вдвое хуже действительности. Гость, ждущий деньги,
              считает дни по написанному, поэтому важно и то, что возврат
              оформляется сразу: задержка не на стороне отеля. */}
          <p>
            При оплате картой возврат оформляется сразу после отмены брони и приходит на
            ту же карту в течение <strong>1–7 рабочих дней</strong>. Срок зависит от банка,
            выпустившего карту, — со стороны отеля и платёжной системы деньги отправляются
            в день отмены.
          </p>
          <p>
            Если за семь рабочих дней средства не поступили, напишите нам: понадобится
            номер брони и последние четыре цифры карты.
          </p>
          <p>
            Полные условия описаны в{" "}
            <Link href="/oferta">публичной оферте</Link>.
          </p>
        </Prose>

        <div className="mt-12 flex flex-wrap gap-3">
          <Link href="/booking" className={buttonClass("primary", "lg")}>
            Забронировать номер
          </Link>
          <Link href="/kontakty" className={buttonClass("outline", "lg")}>
            Связаться с отелем
          </Link>
        </div>
      </div>
    </>
  );
}
