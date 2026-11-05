/**
 * Посадочные страницы и путеводитель по Алматы — на двух языках.
 *
 * Зачем. До 2026-11-05 на сайте было 14 страниц, и все отвечали на один
 * вопрос: «что это за отель». А люди ищут иначе — «гостиница в центре
 * Алматы», «отель для командировки», «как добраться из аэропорта Алматы»,
 * «where to stay in Almaty». По таким запросам выдачу занимают Booking.com
 * и агрегаторы, и с каждой брони через них отель платит комиссию. Одна
 * страница — один запрос: так и поисковику ясно, о чём страница, и
 * человек получает ответ на свой вопрос, а не главную.
 *
 * Правило контента: ни одного факта, которого нет в lib/site.ts, lib/faq.ts
 * или в общеизвестных сведениях о городе. Расстояния — из выверенного
 * списка nearby (site.ts), маршруты из аэропорта — оттуда же. Где точной
 * цифры нет (автобус до Медеу, часы работы канатной дороги), текст ведёт в
 * 2ГИС, а не называет число наугад: расписания меняются, а страница — нет.
 *
 * В тексте работают **жирный** и [ссылка](/путь), а {priceFrom} заменяется
 * на минимальную цену из базы в момент сборки страницы.
 *
 * Адрес каждой статьи обязан стоять в lib/routes.ts → PAGE_PAIRS: по нему
 * строятся языковые пары и переключатель. Проверка — внизу файла.
 */

import { PAGE_PAIRS, type Lang } from "./routes";

export type Block =
  | { type: "h2"; text: string }
  | { type: "p"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "steps"; items: { title: string; text: string }[] }
  | { type: "facts"; items: [label: string, value: string][] }
  /** Карточки номеров с ценами из базы. */
  | { type: "rooms" }
  /** Блок «Как добраться из аэропорта» с маршрутами. */
  | { type: "airport" }
  /** Площадки событий рядом. */
  | { type: "events" }
  /** Список «Рядом с отелем» с расстояниями. */
  | { type: "nearby" }
  /** Кнопки брони, WhatsApp и звонка. */
  | { type: "cta"; text?: string };

export type Article = {
  path: string;
  lang: Lang;
  kind: "landing" | "guide";
  /** <title> — до ~60 символов, бренд допишет шаблон. */
  title: string;
  /** meta description — до ~160 символов. */
  description: string;
  eyebrow: string;
  h1: string;
  lead: string;
  image: string;
  imageAlt: string;
  /** Карточка в путеводителе и в «Читайте также». */
  card: string;
  blocks: Block[];
  faq?: { q: string; a: string }[];
  related: string[];
};

/* ================================================================== */
/*  RU — посадочные страницы                                           */
/* ================================================================== */

const ruLandings: Article[] = [
  {
    path: "/gostinica-v-centre-almaty",
    lang: "ru",
    kind: "landing",
    title: "Гостиница в центре Алматы — от {priceFrom}",
    description:
      "Отель Airis Residence в центре Алматы: 800 м до проспекта Абая, 700 м до метро «Байконур». 34 номера, завтрак, стойка 24/7. Бронь напрямую дешевле, чем на Booking.com.",
    eyebrow: "Центр Алматы",
    h1: "Гостиница в центре Алматы",
    lead: "Airis Residence стоит в Алмалинском районе, на улице Наурызбай батыра, 134/2. До проспекта Абая — 800 метров, до метро «Байконур» — 700, до театра оперы и балета — километр. При этом здание во дворе, и шума улицы в номерах не слышно.",
    image: "/images/hotel/lobby.jpg",
    imageAlt: "Лобби отеля Airis Residence в центре Алматы",
    card: "Где мы стоим, что рядом пешком и почему в номерах тихо.",
    blocks: [
      { type: "h2", text: "Что рядом — пешком" },
      {
        type: "p",
        text: "Расстояния посчитаны по улицам, а не по прямой, и округлены в большую сторону: если написано «10 минут», дойдёте за десять, а не за двадцать.",
      },
      { type: "nearby" },
      { type: "h2", text: "Почему центр, а не окраина" },
      {
        type: "ul",
        items: [
          "**Метро в 9 минутах.** От «Байконура» одна ветка идёт через весь исторический центр — до «Жибек Жолы», где Арбат, Зелёный базар и парк 28 панфиловцев.",
          "**Театры и концерты — пешком.** Театр оперы и балета имени Абая в 12 минутах, Центральный стадион и Дворец спорта — в 18–22. В день концерта, когда такси не поймать, это решает.",
          "**Дорога из аэропорта — около 30 минут** на такси, примерно 3 700 ₸. Есть и автобусы — маршруты расписаны в [путеводителе](/almaty/iz-aeroporta).",
          "**Тихий двор.** Окна выходят не на трассу. Гости в отзывах отдельно пишут, что шума улицы не слышно.",
        ],
      },
      { type: "h2", text: "Номера и цены" },
      {
        type: "p",
        text: "Пять типов номеров — от одноместного Standart Single до Comfort Plus на 30 м², где поместятся трое. В каждом кондиционер, сейф, мини-бар, Wi-Fi и своя ванная комната. Номера от {priceFrom} за ночь.",
      },
      { type: "rooms" },
      { type: "h2", text: "Что входит в стоимость" },
      {
        type: "ul",
        items: [
          "Завтрак — шведский стол с 7:30 до 10:30, есть халяльный вариант.",
          "Стойка регистрации круглосуточно: заселим и ночью.",
          "Бесплатная парковка под видеонаблюдением.",
          "Хранение багажа до заезда и после выезда.",
          "Ежедневная уборка, Wi-Fi без ограничений.",
        ],
      },
      { type: "cta" },
    ],
    faq: [
      {
        q: "Насколько далеко отель от центра Алматы?",
        a: "Отель и есть центр: Алмалинский район, 800 метров до проспекта Абая и 700 метров до метро «Байконур». До театра оперы и балета — около 12 минут пешком.",
      },
      {
        q: "Есть ли парковка?",
        a: "Да, бесплатная круглосуточная парковка у отеля под видеонаблюдением.",
      },
      {
        q: "Где дешевле бронировать — на сайте или на Booking.com?",
        a: "На сайте. Booking.com продаёт те же номера с наценкой площадки, а на официальном сайте её нет. Оплатить бронь можно картой онлайн, в том числе картой иностранного банка.",
      },
    ],
    related: ["/almaty/chto-posmotret-ryadom", "/almaty/iz-aeroporta", "/gostinica-s-zavtrakom"],
  },
  {
    path: "/otel-dlya-komandirovki",
    lang: "ru",
    kind: "landing",
    title: "Отель для командировки в Алматы — счёт юрлицу",
    description:
      "Командировка в Алматы: номер с рабочим столом, завтрак с 7:30, стойка 24/7. Оплата по счёту на юрлицо, акт и счёт-фактура, договор с фиксированными ценами.",
    eyebrow: "Командировки",
    h1: "Отель для командировки в Алматы",
    lead: "Командированному нужно три вещи: выспаться, поработать в номере и вернуться с правильными документами. В Airis Residence всё это есть — плюс центр города, откуда до деловых встреч недалеко.",
    image: "/images/rooms/standart-single/01.jpg",
    imageAlt: "Номер Standart Single с рабочим столом в отеле Airis Residence",
    card: "Номер с рабочим столом, завтрак с 7:30, счёт и закрывающие документы на компанию.",
    blocks: [
      { type: "h2", text: "Для одной поездки" },
      {
        type: "ul",
        items: [
          "**Рабочее место в номере.** В Standart Single — рабочий стол и кресло, в остальных номерах — рабочая зона и розетки у кровати.",
          "**Завтрак с 7:30.** Шведский стол до 10:30 — успеете до первой встречи.",
          "**Заселение в любое время.** Стойка работает круглосуточно: поздний рейс — не проблема. Ранний заезд или поздний выезд — 20 000 ₸, если номер свободен.",
          "**Wi-Fi без ограничений** по всему отелю, бесплатно.",
          "**Документы.** Нужен счёт на компанию и закрывающие документы — скажите при бронировании.",
        ],
      },
      { type: "h2", text: "Если сотрудники ездят регулярно" },
      {
        type: "p",
        text: "Для компаний есть договор: цены на каждую категорию закрепляются, оплата — по счёту на юрлицо, обычно постоплатой. После договора компания получает закрытый кабинет, где сотрудники бронируют сами, а ответственный видит все брони и расходы. Подробнее — на странице [для корпоративных клиентов](/korporativnym-klientam).",
      },
      {
        type: "steps",
        items: [
          { title: "Заявка", text: "Название компании, БИН и примерный объём размещений — в WhatsApp или на почту." },
          { title: "Договор", text: "Цены по категориям и условия оплаты, обычно постоплата в течение 30 дней." },
          { title: "Кабинет", text: "Доступ для ответственного, дальше он сам добавляет коллег." },
        ],
      },
      { type: "h2", text: "Какой номер выбрать" },
      {
        type: "p",
        text: "Одному на пару ночей хватит Standart Single. Если едете вдвоём с коллегой — Standart Twin с двумя раздельными кроватями. На неделю и дольше удобнее Comfort: больше места, отдельная зона отдыха и гардеробная секция. Номера от {priceFrom} за ночь.",
      },
      { type: "rooms" },
      { type: "cta", text: "Нужен счёт на компанию? Напишите в WhatsApp — выставим в день обращения." },
    ],
    faq: [
      {
        q: "Выставляете ли вы счёт на юридическое лицо?",
        a: "Да. Выставим счёт на оплату в день обращения и передадим закрывающие документы: акт выполненных работ и счёт-фактуру. Для счёта нужны название компании, БИН, даты и тип номера.",
      },
      {
        q: "Можно ли заселиться ночью?",
        a: "Да, стойка регистрации работает круглосуточно. Заезд по умолчанию с 14:00; если нужен номер раньше, это ранний заезд — 20 000 ₸ при наличии свободных номеров.",
      },
      {
        q: "Есть ли условия для компаний, которые селят сотрудников постоянно?",
        a: "Да, по договору: фиксированные цены, оплата по счёту и закрытый кабинет для брони. Доступ в кабинет выдаётся после подписания договора.",
      },
    ],
    related: ["/korporativnym-klientam", "/gostinica-v-centre-almaty", "/almaty/iz-aeroporta"],
  },
  {
    path: "/gostinica-ryadom-s-centralnym-stadionom",
    lang: "ru",
    kind: "landing",
    title: "Гостиница у Центрального стадиона Алматы",
    description:
      "Едете на концерт или матч? Airis Residence — 1,7 км до Центрального стадиона, 1,4 км до Дворца спорта имени Балуана Шолака. Обратно пешком, без пробок и поиска такси.",
    eyebrow: "Концерты и матчи",
    h1: "Гостиница рядом с Центральным стадионом",
    lead: "Главные площадки Алматы — в соседних кварталах от отеля. До Центрального стадиона 1,7 км, это около 22 минут пешком. После концерта, когда центр стоит, а такси не вызвать, вы просто идёте в номер.",
    image: "/images/rooms/comfort/01.jpg",
    imageAlt: "Номер Comfort в отеле Airis Residence рядом с Центральным стадионом",
    card: "Пешком до стадиона, Дворца спорта и оперного театра — для тех, кто едет на событие.",
    blocks: [
      { type: "h2", text: "Площадки рядом" },
      { type: "events" },
      { type: "h2", text: "Почему это важно в день события" },
      {
        type: "ul",
        items: [
          "**Обратная дорога.** После большого концерта десятки тысяч человек одновременно ищут такси. Отсюда до номера 20 минут пешком.",
          "**Заселение до события.** Заезд с 14:00, но вещи можно оставить на стойке и раньше — храним багаж бесплатно.",
          "**Поздний выезд на следующий день** — 20 000 ₸, если номер свободен: можно выспаться после концерта.",
          "**Компанией.** В Comfort Plus поместятся трое: третий гость спит на диван-кровати и уже включён в цену.",
        ],
      },
      { type: "h2", text: "Номера" },
      {
        type: "p",
        text: "Номера от {priceFrom} за ночь, завтрак включён. На даты больших событий свободные номера в центре заканчиваются первыми — лучше бронировать, как только купили билет.",
      },
      { type: "rooms" },
      { type: "cta" },
    ],
    faq: [
      {
        q: "Сколько идти от отеля до Центрального стадиона?",
        a: "Около 1,7 км по улицам — примерно 22 минуты пешком. До Дворца спорта имени Балуана Шолака — 1,4 км, около 18 минут.",
      },
      {
        q: "Можно ли оставить вещи до заселения?",
        a: "Да, багаж храним на стойке до заезда и после выезда.",
      },
      {
        q: "Можно ли поселиться втроём?",
        a: "Да, в номере Comfort Plus: третий гость спит на диван-кровати, и он уже включён в стоимость.",
      },
    ],
    related: ["/gostinica-v-centre-almaty", "/almaty/chto-posmotret-ryadom", "/almaty/iz-aeroporta"],
  },
  {
    path: "/gostinica-s-zavtrakom",
    lang: "ru",
    kind: "landing",
    title: "Гостиница с завтраком в Алматы — шведский стол",
    description:
      "Airis Residence: гостиница в центре Алматы с завтраком «шведский стол» с 7:30 до 10:30, есть халяльный вариант. Номера от {priceFrom}, стойка 24/7.",
    eyebrow: "Завтрак включён",
    h1: "Гостиница с завтраком в Алматы",
    lead: "Завтрак в Airis Residence — шведский стол каждое утро с 7:30 до 10:30: горячие блюда, выпечка, нарезки, фрукты и напитки. Есть халяльный вариант. Не нужно искать кафе и считать отдельный чек.",
    image: "/images/breakfast/01.jpg",
    imageAlt: "Завтрак «шведский стол» в отеле Airis Residence",
    card: "Шведский стол с 7:30 до 10:30, халяльный вариант и что ещё входит в цену.",
    blocks: [
      { type: "h2", text: "Как устроен завтрак" },
      {
        type: "facts",
        items: [
          ["Формат", "Шведский стол"],
          ["Время", "С 7:30 до 10:30"],
          ["Что есть", "Горячие блюда, выпечка, нарезки, фрукты, напитки"],
          ["Халяль", "Есть халяльный завтрак"],
          ["Тариф", "В тарифах с завтраком; можно выбрать и без него"],
        ],
      },
      {
        type: "p",
        text: "Гости в отзывах на Яндекс Картах отдельно отмечают завтраки — «разнообразные, сытные». Если завтрак не нужен, при бронировании можно выбрать тариф без него.",
      },
      { type: "h2", text: "Номера" },
      {
        type: "p",
        text: "Пять типов номеров от {priceFrom} за ночь. В каждом кондиционер, сейф, мини-бар, Wi-Fi и своя ванная. Заезд с 14:00, выезд до 12:00.",
      },
      { type: "rooms" },
      { type: "cta" },
    ],
    faq: [
      {
        q: "Во сколько завтрак?",
        a: "С 7:30 до 10:30, шведский стол.",
      },
      {
        q: "Есть ли халяльная еда?",
        a: "Да, кроме шведского стола есть халяльный завтрак.",
      },
      {
        q: "Можно ли забронировать без завтрака?",
        a: "Да, в форме бронирования есть тариф без завтрака.",
      },
    ],
    related: ["/gostinica-v-centre-almaty", "/otel-dlya-komandirovki", "/almaty/chto-posmotret-ryadom"],
  },
  {
    path: "/gostinica-posutochno",
    lang: "ru",
    kind: "landing",
    title: "Гостиница посуточно в центре Алматы — от {priceFrom}",
    description:
      "Номер посуточно в центре Алматы: от одной ночи, заселение круглосуточно, завтрак включён, парковка бесплатно. Бесплатная отмена за 24 часа до заезда.",
    eyebrow: "Посуточно",
    h1: "Гостиница посуточно в центре Алматы",
    lead: "Снять номер на одну ночь или на неделю — без договоров, залогов и встреч с хозяином квартиры. Заселение круглосуточно, уборка каждый день, завтрак уже в цене.",
    image: "/images/rooms/standart/01.jpg",
    imageAlt: "Номер Standart посуточно в отеле Airis Residence",
    card: "От одной ночи: чем номер в отеле удобнее квартиры посуточно.",
    blocks: [
      { type: "h2", text: "Чем номер удобнее квартиры посуточно" },
      {
        type: "ul",
        items: [
          "**Не нужно договариваться о встрече.** Стойка работает 24/7, ключ выдадут в любое время.",
          "**Без залога.** Бронь оплачивается картой онлайн или на месте.",
          "**Уборка каждый день** и смена белья по графику.",
          "**Завтрак включён** в тарифы с завтраком.",
          "**Бесплатная отмена** — не позднее чем за 24 часа до заезда.",
          "**Парковка бесплатно**, под видеонаблюдением.",
        ],
      },
      { type: "h2", text: "Условия" },
      {
        type: "facts",
        items: [
          ["Заезд / выезд", "С 14:00 / до 12:00"],
          ["Ранний заезд, поздний выезд", "20 000 ₸, если номер свободен"],
          ["Оплата", "Наличные, Visa, Mastercard, онлайн картой"],
          ["Отмена", "Бесплатно за 24 часа до заезда"],
          ["Дети", "До 6 лет бесплатно на существующих местах"],
          ["Животные", "Не размещаем"],
        ],
      },
      { type: "h2", text: "Номера и цены за ночь" },
      { type: "rooms" },
      { type: "cta" },
    ],
    faq: [
      {
        q: "Можно ли снять номер на одну ночь?",
        a: "Да, минимального срока нет — бронируйте хоть на одну ночь.",
      },
      {
        q: "Нужен ли залог?",
        a: "Нет. Оплатить бронь можно картой онлайн при бронировании или на месте — наличными или картой.",
      },
      {
        q: "Когда вернутся деньги при отмене?",
        a: "Возврат оформляется в день отмены; на карту деньги приходят за 1–7 рабочих дней — срок зависит от банка.",
      },
    ],
    related: ["/gostinica-v-centre-almaty", "/kak-oplatit", "/almaty/iz-aeroporta"],
  },
];

/* ================================================================== */
/*  RU — путеводитель                                                  */
/* ================================================================== */

const ruGuides: Article[] = [
  {
    path: "/almaty/iz-aeroporta",
    lang: "ru",
    kind: "guide",
    title: "Из аэропорта Алматы в центр: такси, автобус, трансфер",
    description:
      "Из аэропорта Алматы в центр: такси около 30 минут и 3 700 ₸, автобусы 96, 120 и ночной 3 за 120 ₸, трансфер от отеля от 5 000 ₸. Маршруты по данным 2ГИС.",
    eyebrow: "Путеводитель",
    h1: "Как добраться из аэропорта Алматы в центр",
    lead: "Аэропорт Алматы (ALA) — в 17 км от центра. На такси дорога занимает около получаса, на автобусе — около полутора часов. Ниже все варианты с ценами и пересадками до улицы Наурызбай батыра, 134/2.",
    image: "/images/hotel/lobby.jpg",
    imageAlt: "Лобби отеля Airis Residence — конечная точка маршрута из аэропорта",
    card: "Такси, автобусы и трансфер: цены, время в пути и где пересадка.",
    blocks: [
      { type: "airport" },
      { type: "h2", text: "Что выбрать" },
      {
        type: "ul",
        items: [
          "**С багажом и после ночного рейса** — такси или трансфер. Такси удобнее заказать в приложении: цена известна заранее.",
          "**Налегке и не спешите** — автобус 96 с пересадкой на троллейбус: остановка в 6 минутах от терминала.",
          "**Ночью** ходит автобус 3, но редко — примерно раз в час. После полуночи надёжнее такси.",
          "**Хотите, чтобы встретили** — напишите номер рейса в WhatsApp: трансфер от 5 000 ₸, цена зависит от пробок.",
        ],
      },
      { type: "h2", text: "Как платить в автобусе" },
      {
        type: "p",
        text: "Проезд — 120 ₸ по транспортной карте Onay или по QR-коду в приложении Onay. Карту продают в терминалах прямо в аэропорту. Наличными дороже.",
      },
      { type: "h2", text: "Если прилетаете рано" },
      {
        type: "p",
        text: "Заезд в отеле с 14:00. Вещи можно оставить на стойке сразу по приезде — храним бесплатно. Если номер нужен раньше, ранний заезд стоит 20 000 ₸ и возможен, когда номер свободен: лучше предупредить при бронировании.",
      },
      { type: "cta", text: "Нужен трансфер? Напишите номер рейса и время прилёта — встретим." },
    ],
    faq: [
      {
        q: "Сколько стоит такси из аэропорта Алматы до центра?",
        a: "Около 3 700 ₸ до улицы Наурызбай батыра по данным на сентябрь 2026 года, дорога — около 30 минут, в пробки дольше.",
      },
      {
        q: "Какой автобус идёт из аэропорта в центр?",
        a: "До отеля удобнее всего автобус 96 с пересадкой на троллейбус 7 или 30 (около 1,5 часа, 240 ₸ за две поездки) или автобус 120 без пересадок — но до его остановки 23 минуты пешком от терминала. Ночью — автобус 3.",
      },
      {
        q: "Может ли отель организовать трансфер?",
        a: "Да, по запросу: от 5 000 ₸, цена зависит от пробок. Напишите заранее номер рейса и время прилёта.",
      },
    ],
    related: ["/almaty/chto-posmotret-ryadom", "/gostinica-v-centre-almaty", "/almaty/gde-ostanovitsya"],
  },
  {
    path: "/almaty/chto-posmotret-ryadom",
    lang: "ru",
    kind: "guide",
    title: "Что посмотреть в центре Алматы рядом с отелем",
    description:
      "Центр Алматы рядом с Airis Residence: театр оперы и балета, Дворец Республики, музей Кастеева, Кок-Тобе, Арбат и Зелёный базар. Расстояния пешком и как доехать на метро.",
    eyebrow: "Путеводитель",
    h1: "Что посмотреть в центре Алматы рядом с отелем",
    lead: "Отель стоит так, что половину центра можно обойти пешком, а вторую — проехать на метро от станции «Байконур» в 9 минутах от входа. Вот маршрут на день-два, без машины.",
    image: "/images/hotel/detail-01.jpg",
    imageAlt: "Интерьер отеля Airis Residence",
    card: "Театры, музеи, Кок-Тобе, Арбат и Зелёный базар — пешком и на метро.",
    blocks: [
      { type: "h2", text: "Пешком от отеля" },
      { type: "nearby" },
      {
        type: "ul",
        items: [
          "**Театр оперы и балета имени Абая** — 12 минут пешком. Опера и балет, репертуар меняется еженедельно: билеты удобно брать на вечер после прогулки.",
          "**Проспект Абая** — 10 минут. Одна из главных улиц города, отсюда удобно двигаться в любую сторону.",
          "**Дворец Республики** — 24 минуты. Рядом с ним нижняя станция канатной дороги на Кок-Тобе.",
          "**Театр имени Мухтара Ауэзова** — 27 минут, **музей искусств имени Кастеева** — 29 минут: крупнейшее собрание казахстанского искусства.",
        ],
      },
      { type: "h2", text: "Кок-Тобе" },
      {
        type: "p",
        text: "Гора с видом на весь город и горы Заилийского Алатау. Наверх ведёт канатная дорога — нижняя станция у Дворца Республики, это около 24 минут пешком от отеля. Лучшее время — ближе к закату, когда в городе загораются огни.",
      },
      { type: "h2", text: "Арбат, Зелёный базар и парк 28 панфиловцев" },
      {
        type: "p",
        text: "Старый центр удобнее всего проехать на метро: от станции «Байконур» (9 минут от отеля) по единственной ветке до «Жибек Жолы». Там пешеходная улица — Арбат, а рядом Зелёный базар, где пробуют курт, сухофрукты и местные сладости, и парк 28 панфиловцев с деревянным Вознесенским собором.",
      },
      { type: "h2", text: "Совет" },
      {
        type: "p",
        text: "Часы работы музеев, канатной дороги и расписание театров меняются — сверяйтесь с их сайтами или 2ГИС в день визита. На стойке подскажут, как удобнее добраться, круглосуточно.",
      },
      { type: "cta" },
    ],
    faq: [
      {
        q: "Далеко ли от отеля до Кок-Тобе?",
        a: "Нижняя станция канатной дороги на Кок-Тобе — у Дворца Республики, около 1,9 км или 24 минут пешком от отеля.",
      },
      {
        q: "Как добраться до Арбата и Зелёного базара?",
        a: "На метро: от станции «Байконур» (700 м от отеля) по одной ветке до станции «Жибек Жолы».",
      },
    ],
    related: ["/almaty/medeu-i-shymbulak", "/almaty/iz-aeroporta", "/gostinica-ryadom-s-centralnym-stadionom"],
  },
  {
    path: "/almaty/medeu-i-shymbulak",
    lang: "ru",
    kind: "guide",
    title: "Медеу и Шымбулак из центра Алматы: как добраться",
    description:
      "Как поехать на Медеу и Шымбулак из центра Алматы: такси или автобус до Медеу, дальше канатная дорога на Шымбулак. Что взять с собой и когда лучше ехать.",
    eyebrow: "Путеводитель",
    h1: "Медеу и Шымбулак: поездка в горы из центра",
    lead: "Горы в Алматы начинаются прямо за городом. Высокогорный каток Медеу стоит на высоте около 1 700 метров, выше — горнолыжный курорт Шымбулак. Из центра это поездка на полдня, и ехать удобно из отеля.",
    image: "/images/rooms/luxe/01.jpg",
    imageAlt: "Номер Comfort Plus — отдых после поездки в горы",
    card: "Как доехать до Медеу, подняться на Шымбулак и что взять в горы.",
    blocks: [
      { type: "h2", text: "Как добраться до Медеу" },
      {
        type: "ul",
        items: [
          "**На такси** — самый простой вариант: заказ в приложении, адрес — «Медеу».",
          "**На автобусе** — до Медеу из центра ходит городской автобус. Номер маршрута, остановку и время подскажет 2ГИС: расписание меняется по сезону.",
        ],
      },
      { type: "h2", text: "С Медеу на Шымбулак" },
      {
        type: "p",
        text: "От Медеу на Шымбулак поднимается канатная дорога. Зимой там катаются на лыжах и сноуборде, летом гуляют и смотрят на ледники — с верхних станций открывается вид на горы и город внизу.",
      },
      { type: "h2", text: "Что взять с собой" },
      {
        type: "ul",
        items: [
          "Тёплую куртку даже летом: в горах заметно холоднее, чем в городе.",
          "Солнцезащитный крем и очки — на высоте солнце сильнее.",
          "Удобную обувь: на смотровых площадках много ступеней.",
          "Наличные или карту — на канатную дорогу и перекус.",
        ],
      },
      { type: "h2", text: "Когда ехать" },
      {
        type: "p",
        text: "С утра: в выходные к обеду на дорогах в горы бывают пробки, а погода в горах после полудня меняется чаще. После завтрака в отеле (с 7:30) как раз успеваете выехать рано. Часы работы катка и канатной дороги проверяйте на их официальных сайтах — они зависят от сезона.",
      },
      { type: "cta" },
    ],
    faq: [
      {
        q: "Сколько ехать от центра Алматы до Медеу?",
        a: "Зависит от пробок; на такси это короткая поездка за город. Точное время в пути на сегодня покажет приложение такси или 2ГИС.",
      },
      {
        q: "Как подняться с Медеу на Шымбулак?",
        a: "По канатной дороге, которая идёт от Медеу на Шымбулак.",
      },
    ],
    related: ["/almaty/chto-posmotret-ryadom", "/almaty/gde-ostanovitsya", "/gostinica-s-zavtrakom"],
  },
  {
    path: "/almaty/gde-ostanovitsya",
    lang: "ru",
    kind: "guide",
    title: "Где остановиться в Алматы: какой район выбрать",
    description:
      "Какой район Алматы выбрать для проживания: центр (Алмалинский), Медеуский ближе к горам, Бостандыкский для деловых поездок. Плюсы и минусы каждого.",
    eyebrow: "Путеводитель",
    h1: "Где остановиться в Алматы",
    lead: "Алматы большой, и от района зависит, сколько времени уйдёт на дорогу. Коротко: в первый приезд удобнее всего центр — Алмалинский район. Ниже — чем отличаются районы и кому какой подходит.",
    image: "/images/hotel/lobby.jpg",
    imageAlt: "Отель Airis Residence в Алмалинском районе Алматы",
    card: "Центр, горы или деловой район — какой район выбрать для поездки.",
    blocks: [
      { type: "h2", text: "Алмалинский район — исторический центр" },
      {
        type: "p",
        text: "Метро, театры, музеи, Арбат и Зелёный базар — пешком или в пару остановок. Отсюда одинаково удобно ехать и в горы, и в деловые кварталы. **Кому подходит:** первый приезд, короткая поездка, концерты и матчи — Центральный стадион здесь же.",
      },
      { type: "h2", text: "Медеуский район — ближе к горам" },
      {
        type: "p",
        text: "Восток и юго-восток города, проспект Достык, дорога на Медеу и Кок-Тобе. Ближе к горам, но дальше от метро и старого центра. **Кому подходит:** тем, кто едет ради гор и катания.",
      },
      { type: "h2", text: "Бостандыкский район — деловой юг" },
      {
        type: "p",
        text: "Проспект аль-Фараби, бизнес-центры и большие торговые центры. Удобно, если все встречи там, но до старого центра придётся ехать. **Кому подходит:** деловые поездки с офисом на аль-Фараби.",
      },
      { type: "h2", text: "Почему мы советуем центр" },
      {
        type: "ul",
        items: [
          "Метро «Байконур» в 9 минутах — без пробок до старого центра.",
          "Из аэропорта около 30 минут на такси.",
          "Театр оперы и балета, Дворец Республики, стадион — пешком.",
          "Здание во дворе: центр, но тихо.",
        ],
      },
      { type: "nearby" },
      { type: "h2", text: "Номера в Airis Residence" },
      { type: "rooms" },
      { type: "cta" },
    ],
    faq: [
      {
        q: "Какой район Алматы лучше для туриста?",
        a: "В первый приезд — центр, Алмалинский район: метро, театры, музеи и рынки рядом, до аэропорта около 30 минут на такси.",
      },
      {
        q: "Где жить, если еду кататься на Шымбулак?",
        a: "Ближе к горам — Медеуский район. Но из центра до Медеу тоже недалеко на такси, а вечером в центре больше мест, куда пойти.",
      },
    ],
    related: ["/gostinica-v-centre-almaty", "/almaty/chto-posmotret-ryadom", "/almaty/medeu-i-shymbulak"],
  },
];

/* ================================================================== */
/*  EN — landing pages                                                 */
/* ================================================================== */

const enLandings: Article[] = [
  {
    path: "/en/almaty-city-centre-hotel",
    lang: "en",
    kind: "landing",
    title: "Hotel in Almaty City Centre — from {priceFrom}",
    description:
      "Airis Residence in central Almaty: 800 m to Abay Avenue, 700 m to Baikonur metro. 34 rooms, breakfast, 24/7 front desk, English-speaking staff. Cheaper than on Booking.com.",
    eyebrow: "Almaty city centre",
    h1: "A hotel in Almaty city centre",
    lead: "Airis Residence is in the Almaly district, at 134/2 Nauryzbai Batyr Street. Abay Avenue is 800 metres away, Baikonur metro station 700, the Abay Opera and Ballet Theatre one kilometre. Yet the building sits back in a courtyard, so you don't hear the street from your room.",
    image: "/images/hotel/lobby.jpg",
    imageAlt: "Lobby of Airis Residence hotel in central Almaty",
    card: "Where we are, what's within walking distance and why the rooms are quiet.",
    blocks: [
      { type: "h2", text: "Within walking distance" },
      {
        type: "p",
        text: "Distances are measured along the streets, not as the crow flies, and rounded up: if it says 10 minutes, it takes ten, not twenty.",
      },
      { type: "nearby" },
      { type: "h2", text: "Why stay in the centre" },
      {
        type: "ul",
        items: [
          "**Metro 9 minutes away.** From Baikonur station the line runs through the old centre to Zhibek Zholy — for the Arbat pedestrian street, the Green Bazaar and Panfilov Park.",
          "**Walk to theatres and concerts.** The opera house is 12 minutes away, the Central Stadium and the sports palace 18–22 minutes. On concert nights, when taxis are impossible to find, that matters.",
          "**About 30 minutes from the airport** by taxi, roughly 3,700 ₸. Buses run too — see our [airport guide](/en/almaty/airport-to-city-centre).",
          "**A quiet courtyard.** The windows don't face the main road, and guests mention in reviews that they can't hear the street.",
        ],
      },
      { type: "h2", text: "Rooms and prices" },
      {
        type: "p",
        text: "Five room types, from the Standart Single to the 30 m² Comfort Plus that sleeps three. Every room has air conditioning, a safe, a minibar, Wi-Fi and a private bathroom. Rooms from {priceFrom} per night.",
      },
      { type: "rooms" },
      { type: "h2", text: "What's included" },
      {
        type: "ul",
        items: [
          "Breakfast buffet from 7:30 to 10:30, with a halal option.",
          "24/7 front desk — late-night arrivals are fine. The team speaks English.",
          "Free parking with video surveillance.",
          "Luggage storage before check-in and after check-out.",
          "Daily housekeeping and unlimited Wi-Fi.",
        ],
      },
      { type: "cta" },
    ],
    faq: [
      {
        q: "How far is the hotel from the centre of Almaty?",
        a: "The hotel is in the centre: the Almaly district, 800 metres from Abay Avenue and 700 metres from Baikonur metro station. The opera house is about a 12-minute walk.",
      },
      {
        q: "Do the staff speak English?",
        a: "Yes. The front desk team speaks Russian, English and Turkish, and you can message us on WhatsApp in English at any time.",
      },
      {
        q: "Is it cheaper to book here than on Booking.com?",
        a: "Yes. Booking.com sells the same rooms with its own markup; the official website doesn't add one. You can pay online by card, including cards issued by foreign banks.",
      },
    ],
    related: ["/en/almaty/things-to-do-nearby", "/en/almaty/airport-to-city-centre", "/en/almaty/where-to-stay"],
  },
  {
    path: "/en/business-hotel-almaty",
    lang: "en",
    kind: "landing",
    title: "Business Hotel in Almaty — desk, breakfast, invoices",
    description:
      "A business trip to Almaty: rooms with a work desk, breakfast from 7:30, 24/7 check-in, invoices for companies. Central location near Abay Avenue. English-speaking staff.",
    eyebrow: "Business travel",
    h1: "A business hotel in Almaty",
    lead: "On a business trip you need three things: a good night's sleep, a place to work in your room, and the right paperwork afterwards. Airis Residence has all three — plus a central location that keeps your meetings close.",
    image: "/images/rooms/standart-single/01.jpg",
    imageAlt: "Standart Single room with a work desk at Airis Residence",
    card: "Work desk, breakfast from 7:30, 24/7 check-in and invoices for companies.",
    blocks: [
      { type: "h2", text: "For your trip" },
      {
        type: "ul",
        items: [
          "**A place to work.** The Standart Single has a desk and chair; other rooms have a work area and sockets by the bed.",
          "**Breakfast from 7:30.** A buffet until 10:30 — in time for your first meeting.",
          "**Check in at any hour.** The front desk is open 24/7, so a late flight is not a problem. Early check-in or late check-out costs 20,000 ₸, if the room is free.",
          "**Unlimited free Wi-Fi** throughout the hotel.",
          "**English-speaking staff** at the front desk and on WhatsApp.",
        ],
      },
      { type: "h2", text: "Invoices and company stays" },
      {
        type: "p",
        text: "We can issue an invoice to your company and provide closing documents. For companies that send staff regularly there is a contract with fixed rates per room category, payment by invoice and a private booking account. Write to us on WhatsApp or by email to discuss it.",
      },
      { type: "h2", text: "Which room to choose" },
      {
        type: "p",
        text: "For one person and a couple of nights, the Standart Single is enough. Travelling with a colleague — the Standart Twin with two separate beds. For a week or longer, the Comfort gives you more space, a separate seating area and a wardrobe section. Rooms from {priceFrom} per night.",
      },
      { type: "rooms" },
      { type: "cta", text: "Need an invoice for your company? Message us on WhatsApp — we'll prepare it the same day." },
    ],
    faq: [
      {
        q: "Can you issue an invoice to a company?",
        a: "Yes. We issue an invoice on the day you ask and provide closing documents. We need the company name, its details, the dates and the room type.",
      },
      {
        q: "Can I check in late at night?",
        a: "Yes, the front desk is open 24/7. Standard check-in is from 14:00; an earlier check-in costs 20,000 ₸ if the room is free.",
      },
    ],
    related: ["/en/almaty-city-centre-hotel", "/en/almaty/airport-to-city-centre", "/en/almaty/where-to-stay"],
  },
  {
    path: "/en/hotel-near-central-stadium-almaty",
    lang: "en",
    kind: "landing",
    title: "Hotel near Central Stadium Almaty — a 22-minute walk",
    description:
      "Coming for a concert or a match? Airis Residence is 1.7 km from Almaty Central Stadium and 1.4 km from Baluan Sholak Sports Palace. Walk back after the show — no traffic, no taxi hunt.",
    eyebrow: "Concerts and matches",
    h1: "A hotel near Almaty Central Stadium",
    lead: "Almaty's main venues are a few blocks from the hotel. The Central Stadium is 1.7 km away — about a 22-minute walk. After the concert, when the centre is gridlocked and no taxi will come, you simply walk back to your room.",
    image: "/images/rooms/comfort/01.jpg",
    imageAlt: "Comfort room at Airis Residence near Almaty Central Stadium",
    card: "Walk to the stadium, the sports palace and the opera house.",
    blocks: [
      { type: "h2", text: "Venues nearby" },
      { type: "events" },
      { type: "h2", text: "Why it matters on event day" },
      {
        type: "ul",
        items: [
          "**The way back.** After a big concert, tens of thousands of people look for a taxi at once. From here it's a 20-minute walk to your room.",
          "**Drop your bags before the show.** Check-in is from 14:00, but we store luggage at the front desk for free.",
          "**Sleep in the next day.** Late check-out costs 20,000 ₸ if the room is free.",
          "**Coming as three?** The Comfort Plus sleeps three: the third guest uses the sofa bed and is already included in the price.",
        ],
      },
      { type: "h2", text: "Rooms" },
      {
        type: "p",
        text: "Rooms from {priceFrom} per night, breakfast included. On big event dates central hotels sell out first — it's best to book as soon as you have your ticket.",
      },
      { type: "rooms" },
      { type: "cta" },
    ],
    faq: [
      {
        q: "How far is the hotel from Almaty Central Stadium?",
        a: "About 1.7 km along the streets — roughly a 22-minute walk. The Baluan Sholak Sports Palace is 1.4 km, about 18 minutes.",
      },
      {
        q: "Can I leave my luggage before check-in?",
        a: "Yes, we store luggage at the front desk before check-in and after check-out.",
      },
    ],
    related: ["/en/almaty-city-centre-hotel", "/en/almaty/things-to-do-nearby", "/en/almaty/airport-to-city-centre"],
  },
];

/* ================================================================== */
/*  EN — travel guide                                                  */
/* ================================================================== */

const enGuides: Article[] = [
  {
    path: "/en/almaty/airport-to-city-centre",
    lang: "en",
    kind: "guide",
    title: "Almaty Airport to City Centre: taxi, bus or transfer",
    description:
      "Getting from Almaty Airport (ALA) to the city centre: taxi about 30 min and 3,700 ₸, buses 96, 120 and night bus 3 for 120 ₸, or a hotel transfer from 5,000 ₸.",
    eyebrow: "Almaty guide",
    h1: "Almaty Airport to the city centre",
    lead: "Almaty International Airport (ALA) is 17 km from the centre. A taxi takes about half an hour, a bus about an hour and a half. Here are all the options, with prices and changes, to 134/2 Nauryzbai Batyr Street.",
    image: "/images/hotel/lobby.jpg",
    imageAlt: "Lobby of Airis Residence — the end of your ride from the airport",
    card: "Taxi, buses and transfer: prices, travel times and where to change.",
    blocks: [
      { type: "airport" },
      { type: "h2", text: "Which option to choose" },
      {
        type: "ul",
        items: [
          "**With luggage or after a night flight** — a taxi or a transfer. A taxi is easiest to order in an app, so you know the price in advance.",
          "**Travelling light and not in a hurry** — bus 96 with a change to a trolleybus; the stop is 6 minutes from the terminal.",
          "**At night** bus 3 runs, but rarely — about once an hour. After midnight a taxi is more reliable.",
          "**Want to be met?** Send us your flight number on WhatsApp: a transfer costs from 5,000 ₸, depending on traffic.",
        ],
      },
      { type: "h2", text: "Paying on the bus" },
      {
        type: "p",
        text: "A ride costs 120 ₸ with an Onay transport card or the QR code in the Onay app. Cards are sold at terminals in the airport. Paying cash costs more.",
      },
      { type: "h2", text: "Saying the address to a driver" },
      {
        type: "p",
        text: "Show the address in Russian: **Наурызбай батыра, 134/2** (Nauryzbai Batyr St. 134/2). In taxi apps you can also search for “Airis Residence”.",
      },
      { type: "h2", text: "Landing early?" },
      {
        type: "p",
        text: "Check-in is from 14:00. You can leave your bags at the front desk as soon as you arrive — free of charge. If you need the room earlier, early check-in costs 20,000 ₸ when the room is free; let us know when you book.",
      },
      { type: "cta", text: "Need a transfer? Send us your flight number and arrival time — we'll meet you." },
    ],
    faq: [
      {
        q: "How much is a taxi from Almaty Airport to the city centre?",
        a: "About 3,700 ₸ to Nauryzbai Batyr Street as of September 2026; the ride takes about 30 minutes, longer in traffic.",
      },
      {
        q: "Which bus goes from Almaty Airport to the centre?",
        a: "To the hotel, the most convenient is bus 96 with a change to trolleybus 7 or 30 (about 1.5 hours, 240 ₸ for two rides), or bus 120 with no changes — but its stop is a 23-minute walk from the terminal. At night, bus 3.",
      },
      {
        q: "Can the hotel arrange an airport transfer?",
        a: "Yes, on request: from 5,000 ₸, depending on traffic. Send your flight number and arrival time in advance.",
      },
    ],
    related: ["/en/almaty/things-to-do-nearby", "/en/almaty/where-to-stay", "/en/almaty-city-centre-hotel"],
  },
  {
    path: "/en/almaty/things-to-do-nearby",
    lang: "en",
    kind: "guide",
    title: "Things to Do in Central Almaty — on foot and by metro",
    description:
      "Central Almaty from Airis Residence: the opera house, Palace of the Republic, Kasteyev Museum, Kok-Tobe, the Arbat and the Green Bazaar. Walking times and metro tips.",
    eyebrow: "Almaty guide",
    h1: "Things to do in central Almaty",
    lead: "From the hotel you can cover half of the centre on foot and the other half by metro — Baikonur station is 9 minutes from the door. Here is a one- or two-day plan with no car needed.",
    image: "/images/hotel/detail-01.jpg",
    imageAlt: "Interior of Airis Residence hotel",
    card: "Theatres, museums, Kok-Tobe, the Arbat and the Green Bazaar.",
    blocks: [
      { type: "h2", text: "On foot from the hotel" },
      { type: "nearby" },
      {
        type: "ul",
        items: [
          "**Abay Opera and Ballet Theatre** — 12 minutes. Opera and ballet with a programme that changes weekly; easy to book for the evening.",
          "**Abay Avenue** — 10 minutes. One of the city's main streets and a good starting point in any direction.",
          "**Palace of the Republic** — 24 minutes. Next to it is the lower station of the Kok-Tobe cable car.",
          "**Mukhtar Auezov Drama Theatre** — 27 minutes, and the **Kasteyev State Museum of Arts** — 29 minutes, home to the largest collection of Kazakh art.",
        ],
      },
      { type: "h2", text: "Kok-Tobe" },
      {
        type: "p",
        text: "A hill with views over the whole city and the Trans-Ili Alatau mountains. A cable car takes you up from its lower station by the Palace of the Republic, about a 24-minute walk from the hotel. Go towards sunset, when the city lights come on.",
      },
      { type: "h2", text: "The Arbat, Green Bazaar and Panfilov Park" },
      {
        type: "p",
        text: "The old centre is easiest by metro: from Baikonur station (9 minutes from the hotel) take the city's single line to Zhibek Zholy. There you'll find the Arbat pedestrian street, the Green Bazaar — try kurt, dried fruit and local sweets — and Panfilov Park with the wooden Ascension Cathedral.",
      },
      { type: "h2", text: "A tip" },
      {
        type: "p",
        text: "Opening hours of museums and the cable car, and theatre schedules, change — check their websites or 2GIS on the day. The front desk is happy to help with directions, around the clock, in English.",
      },
      { type: "cta" },
    ],
    faq: [
      {
        q: "How far is Kok-Tobe from the hotel?",
        a: "The lower station of the Kok-Tobe cable car is by the Palace of the Republic, about 1.9 km or a 24-minute walk from the hotel.",
      },
      {
        q: "How do I get to the Arbat and the Green Bazaar?",
        a: "By metro: from Baikonur station (700 m from the hotel) take the line to Zhibek Zholy station.",
      },
    ],
    related: ["/en/almaty/medeu-and-shymbulak", "/en/almaty/airport-to-city-centre", "/en/hotel-near-central-stadium-almaty"],
  },
  {
    path: "/en/almaty/medeu-and-shymbulak",
    lang: "en",
    kind: "guide",
    title: "Medeu and Shymbulak from Almaty: how to get there",
    description:
      "How to visit Medeu and Shymbulak from central Almaty: taxi or bus to Medeu, then the cable car up to Shymbulak. What to bring and when to go.",
    eyebrow: "Almaty guide",
    h1: "Medeu and Shymbulak: a mountain day from the centre",
    lead: "In Almaty the mountains start right outside the city. The Medeu high-altitude skating rink sits at about 1,700 metres, and above it is the Shymbulak ski resort. From the centre it's a half-day trip.",
    image: "/images/rooms/luxe/01.jpg",
    imageAlt: "Comfort Plus room — rest after a day in the mountains",
    card: "Getting to Medeu, riding up to Shymbulak and what to bring.",
    blocks: [
      { type: "h2", text: "Getting to Medeu" },
      {
        type: "ul",
        items: [
          "**By taxi** — the simplest option: order in an app and set “Medeu” as the destination.",
          "**By bus** — a city bus runs from the centre to Medeu. Check the route number, stop and times in 2GIS: the schedule changes with the season.",
        ],
      },
      { type: "h2", text: "From Medeu up to Shymbulak" },
      {
        type: "p",
        text: "A cable car runs from Medeu up to Shymbulak. In winter people ski and snowboard there; in summer they hike and look at the glaciers — the upper stations give you views of the peaks and the city below.",
      },
      { type: "h2", text: "What to bring" },
      {
        type: "ul",
        items: [
          "A warm jacket, even in summer: it's noticeably colder in the mountains.",
          "Sunscreen and sunglasses — the sun is stronger at altitude.",
          "Comfortable shoes: the viewpoints have plenty of steps.",
          "A card or some cash for the cable car and a snack.",
        ],
      },
      { type: "h2", text: "When to go" },
      {
        type: "p",
        text: "Early. On weekends the roads to the mountains get busy by lunchtime, and mountain weather changes more often in the afternoon. With breakfast at the hotel from 7:30 you can leave early. Check the rink's and cable car's opening hours on their official websites — they depend on the season.",
      },
      { type: "cta" },
    ],
    faq: [
      {
        q: "How do I get from Medeu to Shymbulak?",
        a: "By the cable car that runs from Medeu up to Shymbulak.",
      },
      {
        q: "Is it cold at Medeu in summer?",
        a: "It's noticeably cooler than in the city, so bring a warm layer even in summer.",
      },
    ],
    related: ["/en/almaty/things-to-do-nearby", "/en/almaty/where-to-stay", "/en/almaty-city-centre-hotel"],
  },
  {
    path: "/en/almaty/where-to-stay",
    lang: "en",
    kind: "guide",
    title: "Where to Stay in Almaty: which area to choose",
    description:
      "Which area of Almaty to stay in: the centre (Almaly), Medeu district near the mountains, or Bostandyk for business. Pros and cons of each, from a local hotel.",
    eyebrow: "Almaty guide",
    h1: "Where to stay in Almaty",
    lead: "Almaty is a big city, and where you stay decides how much time you spend getting around. In short: on a first visit the centre — the Almaly district — is the most convenient. Here is how the areas differ and who each one suits.",
    image: "/images/hotel/lobby.jpg",
    imageAlt: "Airis Residence hotel in Almaty's Almaly district",
    card: "The centre, the mountains or the business district — which area suits your trip.",
    blocks: [
      { type: "h2", text: "Almaly district — the historic centre" },
      {
        type: "p",
        text: "The metro, theatres, museums, the Arbat and the Green Bazaar are all on foot or a few stops away. It's equally easy to head to the mountains or to the business districts from here. **Best for:** a first visit, short trips, concerts and matches — the Central Stadium is right here.",
      },
      { type: "h2", text: "Medeu district — closer to the mountains" },
      {
        type: "p",
        text: "The east and south-east of the city, Dostyk Avenue and the road to Medeu and Kok-Tobe. Closer to the mountains, but further from the metro and the old centre. **Best for:** trips focused on hiking and skiing.",
      },
      { type: "h2", text: "Bostandyk district — the business south" },
      {
        type: "p",
        text: "Al-Farabi Avenue, office towers and large shopping malls. Convenient if all your meetings are there, but you'll need to drive to the old centre. **Best for:** business trips with an office on Al-Farabi.",
      },
      { type: "h2", text: "Why we recommend the centre" },
      {
        type: "ul",
        items: [
          "Baikonur metro station 9 minutes away — no traffic to the old centre.",
          "About 30 minutes from the airport by taxi.",
          "The opera house, the Palace of the Republic and the stadium within walking distance.",
          "The building sits back in a courtyard: central, yet quiet.",
        ],
      },
      { type: "nearby" },
      { type: "h2", text: "Rooms at Airis Residence" },
      { type: "rooms" },
      { type: "cta" },
    ],
    faq: [
      {
        q: "What is the best area in Almaty for tourists?",
        a: "On a first visit, the centre — the Almaly district: the metro, theatres, museums and markets are close, and the airport is about 30 minutes away by taxi.",
      },
      {
        q: "Where should I stay for skiing at Shymbulak?",
        a: "The Medeu district is closest to the mountains. But Medeu is also a short taxi ride from the centre, and the centre has more to do in the evening.",
      },
    ],
    related: ["/en/almaty-city-centre-hotel", "/en/almaty/things-to-do-nearby", "/en/almaty/medeu-and-shymbulak"],
  },
];

export const articles: Article[] = [...ruLandings, ...ruGuides, ...enLandings, ...enGuides];

/* ------------------------------------------------------------------ */

export const articleByPath = (path: string) => articles.find((a) => a.path === path);

export const landings = (lang: Lang) => articles.filter((a) => a.lang === lang && a.kind === "landing");
export const guides = (lang: Lang) => articles.filter((a) => a.lang === lang && a.kind === "guide");

/** Последний сегмент адреса — параметр динамического маршрута. */
export const slugOf = (path: string) => path.split("/").pop() ?? "";

// Каждая статья должна стоять в PAGE_PAIRS (lib/routes.ts): иначе у неё не
// будет языковой пары, переключатель уведёт на главную, а hreflang пропадёт.
// Ошибка всплывает на сборке, а не у гостя.
for (const article of articles) {
  const known = PAGE_PAIRS.some(([ru, en]) => (article.lang === "ru" ? ru : en) === article.path);
  if (!known) throw new Error(`Статья ${article.path} не добавлена в lib/routes.ts → PAGE_PAIRS`);
  for (const link of article.related) {
    const exists =
      articles.some((a) => a.path === link) || PAGE_PAIRS.some(([ru, en]) => ru === link || en === link) ||
      link === "/korporativnym-klientam";
    if (!exists) throw new Error(`Статья ${article.path}: ссылка «Читайте также» на несуществующую ${link}`);
  }
}
