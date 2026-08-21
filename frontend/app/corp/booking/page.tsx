import Link from "next/link";
import { redirect } from "next/navigation";

import { BookingComposer } from "@/components/corp/BookingComposer";
import { CorpHeader } from "@/components/corp/CorpHeader";
import { getDictionary } from "@/lib/corp/dictionary";
import { getCorpLocale, getCorpMe, getCorpRooms } from "@/lib/corp/server";
import { site } from "@/lib/site";

export default async function CorpBookingPage() {
  const locale = await getCorpLocale();
  const dict = getDictionary(locale);

  const [me, roomsResult] = await Promise.all([getCorpMe(), getCorpRooms()]);
  if (!me) redirect("/corp/login");
  const rooms = roomsResult ?? [];

  return (
    <>
      <CorpHeader
        dict={dict}
        locale={locale}
        companyName={me.company.name}
        userName={me.user.fullName || me.user.email}
        isAdmin={me.user.role === "admin"}
      />

      <main className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <Link href="/corp" prefetch={false} className="text-sm text-wine-600 underline underline-offset-4">
          ← {dict.nav.back}
        </Link>

        <h1 className="mt-5 font-display text-[clamp(1.9rem,4vw,2.8rem)] leading-tight font-semibold">
          {dict.booking.title}
        </h1>

        {rooms.length === 0 ? (
          <p className="mt-8 rounded-3xl bg-white p-10 text-center text-ink-700/70 shadow-sm">
            {dict.common.error}
          </p>
        ) : (
          <BookingComposer
            rooms={rooms}
            dict={dict}
            locale={locale}
            hotelName={site.name}
            hotelCity={site.address.city}
          />
        )}
      </main>
    </>
  );
}
