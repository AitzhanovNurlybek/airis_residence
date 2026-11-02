/**
 * Название номера — как есть, без перевода.
 *
 * Сайт переводит Google Translate, и он переводил названия категорий:
 * «Standart Single» на казахском становился «Стандартты бір адамдық», на
 * английском «Standart» — «Standard». А это имена категорий, по которым гость
 * сверяет номер с формой Exely, с Booking.com и с ответами бота. Просьба отеля
 * (2026-11-02): названия на всех языках — латиницей, как в системе.
 */
export function RoomName({ name }: { name: string }) {
  return (
    <span className="notranslate" translate="no">
      {name}
    </span>
  );
}

/** Полное название «Номер "Standart"»: слово «Номер» переводится, имя — нет. */
export function RoomTitle({ name, shortName }: { name: string; shortName: string }) {
  const at = name.indexOf(shortName);
  if (!shortName || at < 0) return <RoomName name={name} />;
  return (
    <>
      {name.slice(0, at)}
      <RoomName name={shortName} />
      {name.slice(at + shortName.length)}
    </>
  );
}
