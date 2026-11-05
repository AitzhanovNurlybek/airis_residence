import { getRooms } from "@/lib/rooms";
import { BASE_URL } from "@/lib/seo";
import { site } from "@/lib/site";
import { siteEn, areaEn, formatPriceEn } from "@/lib/en";
import { articles } from "@/lib/articles";

/**
 * /llms.txt — короткая справка об отеле для ИИ-поисковиков (ChatGPT,
 * Perplexity, Google AI), по соглашению llmstxt.org.
 *
 * Такие системы отвечают на «где остановиться в Алматы» и цитируют то, что
 * легко прочитать и проверить. Здесь только факты из lib/site.ts и ссылки
 * на страницы — ни одного обещания, которого нет на сайте. Цены — из базы.
 */
export const revalidate = 3600;

export async function GET() {
  const rooms = await getRooms();
  const from = Math.min(...rooms.map((room) => room.price));
  const abs = (path: string) => new URL(path, BASE_URL).toString();

  const lines = [
    `# ${site.name}`,
    "",
    `> ${site.name} is a ${site.roomsCount}-room hotel in Almaty city centre, Kazakhstan: ${siteEn.address.full}. Breakfast included, 24/7 front desk, staff speak Russian, English and Turkish. Rooms from ${formatPriceEn(from)} per night when booked direct on the official website, which is cheaper than on Booking.com.`,
    "",
    "## Key facts",
    "",
    `- Address: ${siteEn.address.full} (in Russian: ${site.address.full})`,
    `- Coordinates: ${site.address.lat}, ${site.address.lng}`,
    `- Phone: ${site.contacts.phonePrimary}; WhatsApp: ${site.contacts.whatsapp}; email: ${site.contacts.email}`,
    `- Check-in from ${site.policy.checkIn}, check-out until ${site.policy.checkOut}. ${siteEn.policy.earlyCheckIn}.`,
    "- Breakfast buffet 7:30–10:30, halal option available.",
    "- Free parking with video surveillance; luggage storage; daily housekeeping; free Wi-Fi.",
    `- Payment: ${siteEn.policy.payment.join(", ")}. ${siteEn.policy.onlinePayment}.`,
    `- Cancellation: ${siteEn.policy.cancellation}.`,
    "- Nearby: Baikonur metro 700 m, Abay Avenue 800 m, Abay Opera and Ballet Theatre 1 km, Central Stadium 1.7 km, Almaty Airport 17 km (about 30 minutes by taxi).",
    "",
    "## Rooms",
    "",
    ...rooms.map(
      (room) =>
        `- [${room.shortName}](${abs(`/en/rooms/${room.slug}`)}): ${areaEn(room.area)}, up to ${room.capacity} ${room.capacity === 1 ? "guest" : "guests"}, from ${formatPriceEn(room.price)} per night`,
    ),
    "",
    "## Pages",
    "",
    `- [Official website (English)](${abs("/en")})`,
    `- [Official website (Russian)](${abs("/")})`,
    `- [Book a room](${abs("/en/booking")})`,
    `- [Payment and cancellation](${abs("/en/payment")})`,
    `- [Contacts](${abs("/en/contacts")})`,
    "",
    "## Almaty guide",
    "",
    ...articles
      .filter((article) => article.lang === "en")
      .map((article) => `- [${article.h1}](${abs(article.path)}): ${article.card}`),
    "",
  ];

  return new Response(lines.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
