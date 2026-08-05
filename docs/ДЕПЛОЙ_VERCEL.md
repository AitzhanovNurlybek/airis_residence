# Развёртывание на Vercel

Пошагово, с нуля до работающего сайта на `airisresidence.kz`.

Займёт около часа. Ничего платить не нужно: при объёмах отеля всё
укладывается в бесплатные тарифы.

---

## Почему нужны ещё два сервиса

У Vercel нет постоянного диска: файловая система одноразовая и доступна
только на чтение. Значит, там негде хранить две вещи:

| Что | Куда переносим |
|---|---|
| База (заявки, номера, цены) | Облачный PostgreSQL |
| Фотографии из админки | Объектное хранилище (S3) |

Код это уже умеет — режим переключается переменными окружения. Локально
ничего не меняется: там по-прежнему SQLite и папка `backend/media`.

Ниже — вариант на **Supabase**: там и база, и хранилище в одном аккаунте,
то есть регистрироваться нужно один раз. Если предпочитаете Cloudflare R2
или Neon — код тот же, отличаются только адреса.

---

## Шаг 1. База данных

1. Регистрация на https://supabase.com → **New project**.
   Регион выбрать ближайший — например, Frankfurt.
2. Придумать пароль базы и **сохранить его** — он больше нигде не покажется.
3. Project Settings → **Database** → Connection string → вкладка **URI**.
4. ⚠️ Взять строку **из раздела Connection pooling**, а не прямую.
   В адресе должно быть слово `pooler`. Прямое подключение на Vercel
   быстро упрётся в лимит соединений.
5. Привести строку к виду, который понимает наш код:

```
# было (Supabase отдаёт так):
postgresql://postgres.abcdef:ПАРОЛЬ@aws-0-eu-central-1.pooler.supabase.com:6543/postgres

# нужно (заменить схему и убрать хвост ?sslmode=... если он есть):
postgresql+asyncpg://postgres.abcdef:ПАРОЛЬ@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

Только замена `postgresql://` на `postgresql+asyncpg://`. Больше ничего.

## Шаг 2. Хранилище фотографий

1. В том же проекте Supabase → **Storage** → New bucket.
2. Имя: `media`. **Public bucket — включить** (фотографии на сайте
   должны открываться без авторизации).
3. Project Settings → Storage → **S3 Connection**:
   там будет endpoint и кнопка создать ключи доступа.
4. Записать четыре значения: endpoint, region, access key, secret key.
5. Публичный адрес файлов у Supabase выглядит так:

```
https://<ваш-проект>.supabase.co/storage/v1/object/public/media
```

## Шаг 3. Импорт проекта в Vercel

1. https://vercel.com → **Add New → Project** → выбрать репозиторий
   `airis_residence`.
2. Vercel сам увидит два сервиса — фронтенд и бэкенд, — потому что в корне
   лежит `vercel.json`. Root Directory оставить `./`.
3. **Переменные окружения не забыть до первого деплоя** — см. следующий шаг.

## Шаг 4. Переменные окружения

Settings → Environment Variables. Заполнить для окружения **Production**
(и заодно Preview, если нужны тестовые сборки).

### Для бэкенда

```bash
ROOT_PATH=/api/backend

DATABASE_URL=postgresql+asyncpg://postgres.xxx:ПАРОЛЬ@...pooler.supabase.com:6543/postgres
DATABASE_SSL=true

S3_ENDPOINT=https://<проект>.supabase.co/storage/v1/s3
S3_BUCKET=media
S3_ACCESS_KEY=<ключ из шага 2>
S3_SECRET_KEY=<секрет из шага 2>
S3_REGION=eu-central-1
S3_PUBLIC_BASE=https://<проект>.supabase.co/storage/v1/object/public/media

ADMIN_USERNAME=admin
ADMIN_PASSWORD=<придумать надёжный>
SECRET_KEY=<см. ниже>

CORS_ORIGINS=https://airisresidence.kz,https://www.airisresidence.kz

TELEGRAM_BOT_TOKEN=<от @BotFather, необязательно>
TELEGRAM_CHAT_ID=<от @userinfobot, необязательно>
```

`SECRET_KEY` сгенерировать командой:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Для фронтенда

```bash
BACKEND_URL=https://airisresidence.kz/api/backend
NEXT_PUBLIC_MEDIA_BASE=https://<проект>.supabase.co/storage/v1/object/public/media
```

> До подключения домена в `BACKEND_URL` временно указать выданный
> Vercel адрес вида `https://airis-residence.vercel.app/api/backend`,
> потом заменить на настоящий.

## Шаг 5. Первый деплой и проверка

Deploy. После сборки открыть:

```
https://<адрес>/api/backend/health
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "admin_configured": true,
  "payments_configured": false,
  "telegram_configured": true
}
```

`admin_configured: true` — пароль и ключ подхватились.

Если вместо этого **404** — значит площадка обрезает префикс сама.
Убрать `ROOT_PATH` из переменных, передеплоить.

Дальше проверить по порядку:

1. Главная страница открывается, номера и цены на месте.
2. `/admin` → вход по логину и паролю из переменных.
3. Изменить цену любого номера → открыть сайт → цена новая.
4. Загрузить фотографию → она появилась в карточке номера.

Четвёртый пункт самый важный: он проверяет, что S3 подключён верно.
Если фото не грузится, смотреть логи функции в Vercel — там будет
понятное сообщение.

## Шаг 6. Домен

1. Vercel → Settings → **Domains** → добавить `airisresidence.kz` и `www.airisresidence.kz`.
2. Vercel покажет, какие DNS-записи нужны.
3. Кабинет hoster.kz → домен `airisresidence.kz` → **Управление ресурсными
   записями** → вписать их.
   ⚠️ **MX-записи не трогать** — иначе перестанет работать почта на домене.
4. У `airisresidence.kz` поставить **Primary Domain**, чтобы технический
   адрес `.vercel.app` редиректил на основной. Иначе поисковики увидят
   два одинаковых сайта.
5. После подключения домена заменить `BACKEND_URL` на
   `https://airisresidence.kz/api/backend` и передеплоить.

SSL Vercel выпустит сам.

---

## После запуска

- Старый сайт на WordPress **не удалять**, пока новый не проработает
  хотя бы неделю. Если что-то пойдёт не так, вернуть старую A-запись —
  дело часа.
- Хостинг Эконом-2 на hoster.kz больше не нужен. Оплачен до 25.07.27 —
  можно просто не продлевать. Если на нём почта — оставить ради неё.
- Отправить sitemap в Google Search Console и Яндекс.Вебмастер:
  `https://airisresidence.kz/sitemap.xml`

## Что делать, если

**Админка пишет «не подключена».** Не задан `BACKEND_URL` у фронтенда.

**Вход в админку не проходит, хотя пароль верный.** Не задан `SECRET_KEY`
или не совпадает окружение (задали только для Preview, а смотрите Production).

**Номера на сайте есть, но старые.** Фронтенд не достучался до бэкенда и
показывает запасной список из `lib/site.ts`. Проверить `BACKEND_URL` и
открыть `/api/backend/health`.

**Фотографии загружаются, но не отображаются.** Бакет не публичный
(шаг 2) либо `NEXT_PUBLIC_MEDIA_BASE` не совпадает с `S3_PUBLIC_BASE`.

**Ошибка про prepared statement.** Взята прямая строка подключения вместо
пулера. Вернуться к шагу 1, пункт 4.
