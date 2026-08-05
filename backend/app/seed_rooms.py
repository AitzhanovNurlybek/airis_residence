"""
Первичное наполнение таблицы номеров.

Запускается один раз при старте, если таблица пуста. Дальше источник
правды — база, и этот файл больше ни на что не влияет: правки из админки
он не перетирает.

Данные совпадают с `frontend/lib/site.ts` — тем самым запасным вариантом,
который сайт показывает, когда API недоступен.
"""

"""
Переводы номеров.

Заполняются при первом запуске вместе с номерами. Дальше правятся
в админке на вкладках «Қазақша» и «English». Пустое поле означает
«показать русский вариант».

⚠️ Казахский перевод машинный, требует вычитки носителем языка.
"""

TRANSLATIONS: dict[str, dict] = {
    "standart-single": {
        "kk": {
            "name": "«Standart Single» нөмірі",
            "shortName": "Standart Single",
            "beds": "Бір жалғыз кровать",
            "summary": "Бірнеше түнге іссапарға арналған шағын бір орындық нөмір.",
            "description": "Жұмыс үстелі және толыққанды жуынатын бөлмесі бар бір орындық нөмір. Қысқа іссапарға қажеттінің бәрі: тыныштық, жылдам интернет және таңертеңгі ас.",
            "features": [
                "Бір орындық кровать",
                "Жұмыс үстелі мен кресло",
                "Сейф",
                "Кондиционер",
                "Теледидар",
                "Wi-Fi",
                "Душ, фен, косметикалық керек-жарақтар",
            ],
        },
        "en": {
            "name": "Standart Single room",
            "shortName": "Standart Single",
            "beds": "One single bed",
            "summary": "A compact single room for a business trip of a night or two.",
            "description": "A single room with a work desk and a full private bathroom. Everything a short business trip needs: quiet, fast internet and breakfast in the morning.",
            "features": [
                "Single bed",
                "Work desk and chair",
                "Safe",
                "Air conditioning",
                "TV",
                "Wi-Fi",
                "Shower, hairdryer, toiletries",
            ],
        },
    },
    "standart": {
        "kk": {
            "name": "«Standart» нөмірі",
            "shortName": "Standart",
            "beds": "Екі орындық кровать 180×200",
            "summary": "180×200 екі орындық кровать, мини-бар және сейф. Қонақтардың көбі таңдайтын базалық нұсқа.",
            "description": "Қысқа мерзімді тұруға арналған жайлы әрі ыңғайлы нөмір. Үлкен кровать, бас жағындағы жұмсақ жарық, жұмыс аймағы және кровать жанындағы розеткалар.",
            "features": [
                "Екі орындық кровать 180×200",
                "Сейф және мини-бар",
                "Теледидар, кондиционер, Wi-Fi",
                "Душы бар жуынатын бөлме, фен",
                "Косметикалық керек-жарақтар",
                "Жұмыс аймағы, кровать жанындағы розеткалар",
            ],
        },
        "en": {
            "name": "Standart room",
            "shortName": "Standart",
            "beds": "Double bed 180×200",
            "summary": "A 180×200 double bed, minibar and safe. The room most guests choose.",
            "description": "A comfortable, practical room for a short stay. A large bed, soft reading light at the headboard, a work area and power sockets right by the bed.",
            "features": [
                "Double bed 180×200",
                "Safe and minibar",
                "TV, air conditioning, Wi-Fi",
                "Bathroom with shower, hairdryer",
                "Toiletries",
                "Work area, sockets by the bed",
            ],
        },
    },
    "standart-twin": {
        "kk": {
            "name": "«Standart Twin» нөмірі",
            "shortName": "Standart Twin",
            "beds": "Екі бөлек кровать",
            "summary": "Екі бөлек кровать — іссапардағы әріптестерге немесе достарға.",
            "description": "Екі бөлек кроваты бар, ауданы үлкенірек нөмір. Екеуі жұмыс бабымен келгенде және бөлек ұйықтайтын орын қажет болғанда ыңғайлы.",
            "features": [
                "Екі бір орындық кровать",
                "Сейф және мини-бар",
                "Теледидар, кондиционер, Wi-Fi",
                "Душы бар жуынатын бөлме, фен",
                "Жұмыс аймағы",
                "Креслосы бар демалыс аймағы",
            ],
        },
        "en": {
            "name": "Standart Twin room",
            "shortName": "Standart Twin",
            "beds": "Two single beds",
            "summary": "Two separate beds — for colleagues on a business trip or friends travelling together.",
            "description": "A larger room with two separate beds. Convenient when two people travel for work and need their own sleeping space.",
            "features": [
                "Two single beds",
                "Safe and minibar",
                "TV, air conditioning, Wi-Fi",
                "Bathroom with shower, hairdryer",
                "Work area",
                "Seating area with an armchair",
            ],
        },
    },
    "comfort": {
        "kk": {
            "name": "«Comfort» нөмірі",
            "shortName": "Comfort",
            "beds": "Екі орындық кровать 180×200",
            "summary": "Кеңірек аудан, бөлек демалыс аймағы және кеңейтілген жабдық.",
            "description": "Бір түннен ұзақ қалатындарға арналған кең нөмір. Бөлек демалыс аймағы, үлкейтілген жұмыс аймағы және толыққанды киім шкафы.",
            "features": [
                "Екі орындық кровать 180×200",
                "Креслосы бар демалыс аймағы",
                "Сейф және мини-бар",
                "Теледидар, кондиционер, Wi-Fi",
                "Душы бар жуынатын бөлме, фен",
                "Киім шкафы",
            ],
        },
        "en": {
            "name": "Comfort room",
            "shortName": "Comfort",
            "beds": "Double bed 180×200",
            "summary": "More space, a separate seating area and extended amenities.",
            "description": "A spacious room for those staying longer than a night. A separate seating area, a larger work space and a full wardrobe section.",
            "features": [
                "Double bed 180×200",
                "Seating area with an armchair",
                "Safe and minibar",
                "TV, air conditioning, Wi-Fi",
                "Bathroom with shower, hairdryer",
                "Wardrobe section",
            ],
        },
    },
    "luxe": {
        "kk": {
            "name": "«Luxe» нөмірі",
            "shortName": "Luxe",
            "beds": "Екі орындық кровать 180×200",
            "summary": "Қонақүйдің ең үлкен нөмірі: қонақ бөлмесі аймағы, премиум әрлеу, қалаға көрініс.",
            "description": "Бөлек қонақ бөлмесі аймағы және премиум әрлеуі бар 30 м² люкс. Ұзақ тұруға және кеңістік маңызды қонақтарға қолайлы.",
            "features": [
                "Екі орындық кровать 180×200",
                "Бөлек қонақ бөлмесі аймағы",
                "Сейф және мини-бар",
                "Теледидар, кондиционер, Wi-Fi",
                "Кең жуынатын бөлме",
                "Халаттар мен тәпішкелер",
                "Жұмыс орны",
            ],
        },
        "en": {
            "name": "Luxe suite",
            "shortName": "Luxe",
            "beds": "Double bed 180×200",
            "summary": "The largest room in the hotel: a living area, premium finishes and a city view.",
            "description": "A 30 m² suite with a dedicated living area and premium finishes. Suited to longer stays and to guests who value space.",
            "features": [
                "Double bed 180×200",
                "Dedicated living area",
                "Safe and minibar",
                "TV, air conditioning, Wi-Fi",
                "Spacious bathroom",
                "Bathrobes and slippers",
                "Work space",
            ],
        },
    },
}

SEED_ROOMS: list[dict] = [
    {
        "slug": "standart-single",
        "name": 'Номер "Standart Single"',
        "short_name": "Standart Single",
        "price": 25000,
        "area": "16–18 м²",
        "capacity": 1,
        "beds": "Одна односпальная кровать",
        "summary": "Компактный одноместный номер для деловой поездки на пару ночей.",
        "description": (
            "Одноместный номер с рабочим столом и полноценной ванной комнатой. "
            "Всё, что нужно для короткой командировки: тишина, быстрый интернет "
            "и завтрак с утра."
        ),
        "features": [
            "Односпальная кровать",
            "Рабочий стол и кресло",
            "Сейф",
            "Кондиционер",
            "Телевизор",
            "Wi-Fi",
            "Душ, фен, косметические принадлежности",
        ],
        "images": [
            "/images/rooms/standart-single/01.jpg",
            "/images/rooms/standart-single/02.jpg",
            "/images/rooms/standart-single/03.jpg",
            "/images/rooms/standart-single/04.jpg",
        ],
    },
    {
        "slug": "standart",
        "name": 'Номер "Standart"',
        "short_name": "Standart",
        "price": 45000,
        "area": "18–20 м²",
        "capacity": 2,
        "beds": "Двуспальная кровать 180×200",
        "summary": "Двуспальная кровать 180×200, мини-бар и сейф. Базовый выбор большинства гостей.",
        "description": (
            "Уютный и функциональный номер для краткосрочного проживания. "
            "Большая кровать, мягкий свет у изголовья, рабочая зона и розетки "
            "прямо у кровати."
        ),
        "features": [
            "Двуспальная кровать 180×200",
            "Сейф и мини-бар",
            "Телевизор, кондиционер, Wi-Fi",
            "Ванная комната с душем, фен",
            "Косметические принадлежности",
            "Рабочая зона, розетки у кровати",
        ],
        "images": [
            "/images/rooms/standart/01.jpg",
            "/images/rooms/standart/02.jpg",
            "/images/rooms/standart/03.jpg",
            "/images/rooms/standart/04.jpg",
        ],
    },
    {
        "slug": "standart-twin",
        "name": 'Номер "Standart Twin"',
        "short_name": "Standart Twin",
        "price": 45000,
        "area": "23 м²",
        "capacity": 2,
        "beds": "Две раздельные кровати",
        "summary": "Две раздельные кровати — для коллег в командировке или друзей.",
        "description": (
            "Номер с двумя раздельными кроватями и увеличенной площадью. Удобен, "
            "когда едут вдвоём по работе и нужны отдельные спальные места."
        ),
        "features": [
            "Две односпальные кровати",
            "Сейф и мини-бар",
            "Телевизор, кондиционер, Wi-Fi",
            "Ванная комната с душем, фен",
            "Рабочая зона",
            "Зона отдыха с креслом",
        ],
        "images": [
            "/images/rooms/standart-twin/01.jpg",
            "/images/rooms/standart-twin/02.jpg",
        ],
    },
    {
        "slug": "comfort",
        "name": 'Номер "Comfort"',
        "short_name": "Comfort",
        "price": 50000,
        "area": "25 м²",
        "capacity": 2,
        "beds": "Двуспальная кровать 180×200",
        "summary": "Больше площади, отдельная зона отдыха и расширенное оснащение.",
        "description": (
            "Просторный номер для тех, кто остаётся дольше, чем на ночь. Отдельная "
            "зона отдыха, увеличенная рабочая зона и полноценная гардеробная секция."
        ),
        "features": [
            "Двуспальная кровать 180×200",
            "Зона отдыха с креслом",
            "Сейф и мини-бар",
            "Телевизор, кондиционер, Wi-Fi",
            "Ванная комната с душем, фен",
            "Гардеробная секция",
        ],
        "images": [
            "/images/rooms/comfort/01.jpg",
            "/images/rooms/comfort/02.jpg",
            "/images/rooms/comfort/03.jpg",
        ],
    },
    {
        "slug": "luxe",
        "name": 'Номер "Luxe"',
        "short_name": "Luxe",
        "price": 70000,
        "area": "30 м²",
        "capacity": 2,
        "beds": "Двуспальная кровать 180×200",
        "summary": "Самый большой номер отеля: гостиная зона, премиальная отделка, вид на город.",
        "description": (
            "Люкс на 30 м² с выделенной гостиной зоной и премиальной отделкой. "
            "Подходит для длительного проживания и для гостей, которым важно пространство."
        ),
        "features": [
            "Двуспальная кровать 180×200",
            "Выделенная гостиная зона",
            "Сейф и мини-бар",
            "Телевизор, кондиционер, Wi-Fi",
            "Просторная ванная комната",
            "Халаты и тапочки",
            "Рабочее место",
        ],
        "images": [
            "/images/rooms/luxe/01.jpg",
            "/images/rooms/luxe/02.jpg",
            "/images/rooms/luxe/03.jpg",
        ],
    },
]
