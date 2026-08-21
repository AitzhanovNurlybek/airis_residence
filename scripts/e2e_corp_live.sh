#!/usr/bin/env bash
#
# Живая проверка корпоративного кабинета: настоящий бэкенд, собранный Next,
# настоящий вход через httpOnly-куку.
#
# Дополняет backend/e2e_corp.py, который гоняет API в одном процессе. Здесь
# проверяется то, чего тот не видит: прокси между браузером и FastAPI, куки,
# редиректы неавторизованного, переключение языка и то, что публичный сайт с
# админкой не задеты.
#
# Запуск (из любой папки):  bash scripts/e2e_corp_live.sh
# Перед запуском нужен свежий фронт:  cd frontend && npx next build
#
# Работает на отдельной базе (_corp_live.db) и подменённых доступах: локальную
# базу и боевую не трогает.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$ROOT/backend/_corp_live_tmp"
BACK_PORT=8000
FRONT_PORT=3010

# Питон из виртуального окружения бэкенда: на Windows он в Scripts/, иначе в bin/.
PY="$ROOT/backend/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$ROOT/backend/.venv/bin/python"
[ -x "$PY" ] || { echo "Не найден python в backend/.venv"; exit 1; }

# Порт освобождаем по слушателю, а не kill по PID.
#
# Это не перестраховка: `npx next start` запускает node отдельным процессом, и
# kill убивает только обёртку. Node остаётся держать порт, следующий запуск
# молча не биндится — и тест идёт против СТАРОГО сервера, то есть против старой
# сборки. Один раз это стоило получаса разбора «почему падает уже исправленное».
free_port() {
  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort $1 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
  else
    fuser -k "$1/tcp" >/dev/null 2>&1
  fi
}

cleanup() {
  free_port "$FRONT_PORT"
  free_port "$BACK_PORT"
  rm -rf "$T"
  rm -f "$ROOT/backend/_corp_live.db"
}
trap cleanup EXIT
free_port "$FRONT_PORT"
free_port "$BACK_PORT"
mkdir -p "$T"

ok=0; bad=0
check() { if [ "$1" = "1" ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; bad=$((bad+1)); fi; }
has() { grep -qa "$2" "$1" && echo 1 || echo 0; }


# ─────────────────────────── Бэкенд и данные ───────────────────────────

cd "$ROOT/backend" || exit 1
rm -f _corp_live.db
DATABASE_URL="sqlite+aiosqlite:///./_corp_live.db" \
ADMIN_USERNAME="admin" ADMIN_PASSWORD="live-admin-pass" \
SECRET_KEY="live-secret-key-long-enough-for-hmac" \
TELEGRAM_BOT_TOKEN="" TELEGRAM_CHAT_ID="" \
  "$PY" -m uvicorn app.main:app --port "$BACK_PORT" --log-level warning >"$T/back.log" 2>&1 &
curl -s --retry 40 --retry-delay 1 --retry-connrefused -o /dev/null "http://127.0.0.1:$BACK_PORT/health" || {
  echo "БЭКЕНД НЕ ПОДНЯЛСЯ"; cat "$T/back.log"; exit 1; }

TOKEN=$(curl -s -X POST "http://127.0.0.1:$BACK_PORT/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"live-admin-pass"}' \
  | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('token',''))")
[ -n "$TOKEN" ] || { echo "НЕТ ТОКЕНА АДМИНА"; exit 1; }

# Тело с кириллицей передаём файлом, а не аргументом: Windows-curl перекодирует
# аргументы по кодовой странице консоли, и JSON приезжает битым — бэкенд
# отвечает «There was an error parsing the body».
cat > "$T/company.json" <<'JSON'
{"slug":"company-a","name":"ТОО «Компания-пример А»","bin":"000000000001","contractNumber":"№001","contractDate":"2026-01-15","paymentTerms":"постоплата, 30 дн. (после услуг)","managerName":"Отдел бронирования Airis","managerEmail":"airisresidence-kz@gmail.com","managerPhone":"+7 (700) 000 0001","discountPercent":12}
JSON
cat > "$T/user.json" <<'JSON'
{"email":"admin@company-a.example","fullName":"Айгуль Ответственная","role":"admin","password":"corp-pass-12345"}
JSON

curl -s -X POST "http://127.0.0.1:$BACK_PORT/api/admin/corp/companies" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary @"$T/company.json" -o "$T/co.json"
curl -s -X POST "http://127.0.0.1:$BACK_PORT/api/admin/corp/companies/company-a/users" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary @"$T/user.json" -o "$T/u.json"
grep -qa '"slug"' "$T/co.json" || { echo "КОМПАНИЯ НЕ СОЗДАНА:"; cat "$T/co.json"; exit 1; }
echo "бэкенд поднят, компания и сотрудник заведены"

# ──────────────────────────────── Фронт ────────────────────────────────

cd "$ROOT/frontend" || exit 1
BACKEND_URL="http://127.0.0.1:$BACK_PORT" npx next start --port "$FRONT_PORT" >"$T/front.log" 2>&1 &
curl -s --retry 60 --retry-delay 1 --retry-connrefused -o /dev/null "http://127.0.0.1:$FRONT_PORT/" || {
  echo "ФРОНТ НЕ ПОДНЯЛСЯ"; cat "$T/front.log"; exit 1; }
grep -qa "EADDRINUSE" "$T/front.log" && {
  echo "ПОРТ $FRONT_PORT ЗАНЯТ ЧУЖИМ ПРОЦЕССОМ — тест пошёл бы против старой сборки"; exit 1; }
echo "фронт поднят"

F="http://127.0.0.1:$FRONT_PORT"

echo
echo "── Вход ──"
code=$(curl -s -o "$T/login.html" -w "%{http_code}" "$F/corp/login")
check "$([ "$code" = "200" ] && echo 1 || echo 0)" "страница входа отдаёт 200 (получили $code)"
check "$(has "$T/login.html" 'Корпоративный раздел портала')" "заголовок формы входа на месте"

curl -s -L -o "$T/anon.html" "$F/corp"
check "$(has "$T/anon.html" 'Корпоративный раздел портала')" "без входа кабинет уводит на форму"

curl -s -X POST "$F/api/corp/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@company-a.example","password":"wrong-password"}' -o "$T/bad.json"
check "$(has "$T/bad.json" 'error')" "неверный пароль не пускает"

curl -s -c "$T/jar" -X POST "$F/api/corp/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@company-a.example","password":"corp-pass-12345"}' -o "$T/ok.json"
check "$(has "$T/ok.json" '"ok":true')" "вход через прокси фронта"
check "$(has "$T/jar" 'airis_corp')" "кука сессии поставлена"
check "$(has "$T/jar" '#HttpOnly_')" "кука httpOnly — скриптом не украсть"

echo
echo "── Кабинет ──"
curl -s -b "$T/jar" -o "$T/cab.html" "$F/corp"
check "$(has "$T/cab.html" 'Кабинет компании')" "кабинет открылся"
check "$(has "$T/cab.html" 'Компания-пример А')" "карточка компании"
check "$(has "$T/cab.html" 'постоплата')" "условия оплаты видны"
check "$(has "$T/cab.html" 'заявка уходит менеджеру')" "честная плашка про подтверждение"
check "$(has "$T/cab.html" 'airisresidence-kz@gmail.com')" "менеджер отеля указан"

curl -s -b "$T/jar" -o "$T/bk.html" "$F/corp/bookings"
check "$(has "$T/bk.html" 'Мои бронирования')" "страница броней открылась"
check "$(has "$T/bk.html" 'Бронирований пока нет')" "пустое состояние показано"

echo
echo "── Подбор номеров ──"
curl -s -b "$T/jar" -o "$T/pick.html" "$F/corp/booking"
check "$(has "$T/pick.html" 'Новое бронирование')" "экран подбора открылся"
# Комментарий JSX, поставленный не в те скобки, печатается на странице как
# обычный текст — сборка про это молчит. Ловим служебный мусор в разметке.
check "$(grep -qa 'eslint-disable\|next/image' "$T/pick.html" && echo 0 || echo 1)" "служебных комментариев в тексте нет"
check "$(has "$T/pick.html" 'Standart')" "номера показаны"
# Прайс компании: скидка 12 % от 45 000 округляется вниз до сотни = 39 600.
# Суммы печатаются с неразрывным пробелом: так и задумано, иначе число
# рвётся переносом строки посередине. В UTF-8 он занимает ДВА байта, а grep
# здесь работает побайтово — отсюда две точки в шаблоне вместо пробела.
check "$(has "$T/pick.html" '39..600')" "корпоративная цена посчитана и показана"
check "$(has "$T/pick.html" '45..000')" "публичная цена рядом — выгода видна"

echo
echo "── Оформление брони ──"
IN=$(date -d "+10 days" +%F)
OUT=$(date -d "+13 days" +%F)
cat > "$T/booking.json" <<JSON
{"checkIn":"$IN","checkOut":"$OUT","adults":2,"children":0,"guestName":"Guest","guestPhone":"+7 700 000 00 00","comment":"","items":[{"roomSlug":"comfort","roomsCount":1}]}
JSON
curl -s -b "$T/jar" -X POST "$F/api/corp/bookings" \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary @"$T/booking.json" -o "$T/nb.json"
check "$(has "$T/nb.json" '"number":"K-')" "бронь создана через прокси"
check "$(has "$T/nb.json" '"nights":3')" "ночей посчитано верно"
check "$(has "$T/nb.json" '"status":"new"')" "статус — заявка, а не подтверждение"

# Цена в строке брони — снимок: она не должна зависеть от того, что потом
# поменяют в прайсе.
check "$(has "$T/nb.json" '"pricePerNight"')" "цена зафиксирована в строке брони"

curl -s -b "$T/jar" -o "$T/bk2.html" "$F/corp/bookings"
check "$(has "$T/bk2.html" 'K-0001')" "бронь видна в истории"
check "$(has "$T/bk2.html" 'Ожидает подтверждения')" "статус подписан по-человечески"

# Заявка на прошедшую дату уходить не должна.
cat > "$T/past.json" <<'JSON'
{"checkIn":"2020-01-01","checkOut":"2020-01-03","adults":1,"items":[{"roomSlug":"comfort","roomsCount":1}]}
JSON
pcode=$(curl -s -b "$T/jar" -X POST "$F/api/corp/bookings" \
  -H 'Content-Type: application/json' --data-binary @"$T/past.json" -o /dev/null -w "%{http_code}")
check "$([ "$pcode" = "400" ] && echo 1 || echo 0)" "прошедшая дата отклонена (получили $pcode)"

# Номер на одного не должен принимать пятерых.
cat > "$T/over.json" <<JSON
{"checkIn":"$IN","checkOut":"$OUT","adults":5,"items":[{"roomSlug":"standart-single","roomsCount":1}]}
JSON
ocode=$(curl -s -b "$T/jar" -X POST "$F/api/corp/bookings" \
  -H 'Content-Type: application/json' --data-binary @"$T/over.json" -o /dev/null -w "%{http_code}")
check "$([ "$ocode" = "400" ] && echo 1 || echo 0)" "перебор гостей отклонён (получили $ocode)"

echo
echo "── Сотрудники ──"
curl -s -b "$T/jar" -o "$T/emp.html" "$F/corp/employees"
check "$(has "$T/emp.html" 'Сотрудники')" "раздел сотрудников открылся"
check "$(has "$T/emp.html" 'admin@company-a.example')" "ответственный в списке"

cat > "$T/newemp.json" <<'JSON'
{"email":"driver@company-a.example","fullName":"Ержан Сотрудник","role":"employee","password":"staff-pass-123"}
JSON
curl -s -b "$T/jar" -X POST "$F/api/corp/employees" \
  -H 'Content-Type: application/json; charset=utf-8' \
  --data-binary @"$T/newemp.json" -o "$T/ne.json"
check "$(has "$T/ne.json" 'driver@company-a.example')" "сотрудник заведён"

curl -s -c "$T/jar3" -X POST "$F/api/corp/login" -H 'Content-Type: application/json' \
  -d '{"email":"driver@company-a.example","password":"staff-pass-123"}' -o "$T/le.json"
check "$(has "$T/le.json" '"ok":true')" "новый сотрудник входит"

# Рядовой сотрудник не видит чужих броней и не управляет коллегами.
curl -s -b "$T/jar3" -o "$T/ebk.json" "$F/api/corp/bookings"
check "$([ "$(cat "$T/ebk.json")" = "[]" ] && echo 1 || echo 0)" "чужие брони сотруднику не видны"
ecode=$(curl -s -b "$T/jar3" -o /dev/null -w "%{http_code}" "$F/api/corp/employees")
check "$([ "$ecode" = "403" ] && echo 1 || echo 0)" "список сотрудников ему закрыт (получили $ecode)"
curl -s -b "$T/jar3" -L -o "$T/eredir.html" "$F/corp/employees"
check "$(grep -qa 'Сотрудники' "$T/eredir.html" && echo 0 || echo 1)" "страница сотрудников его уводит в кабинет"

echo
echo "── Смена пароля ──"
wcode=$(curl -s -b "$T/jar3" -X POST "$F/api/corp/password" -H 'Content-Type: application/json' \
  -d '{"current_password":"wrong","new_password":"another-pass-123"}' -o /dev/null -w "%{http_code}")
check "$([ "$wcode" = "400" ] && echo 1 || echo 0)" "неверный текущий пароль не принят (получили $wcode)"

ncode=$(curl -s -b "$T/jar3" -X POST "$F/api/corp/password" -H 'Content-Type: application/json' \
  -d '{"current_password":"staff-pass-123","new_password":"another-pass-123"}' -o /dev/null -w "%{http_code}")
check "$([ "$ncode" = "204" ] && echo 1 || echo 0)" "пароль сменён (получили $ncode)"

curl -s -X POST "$F/api/corp/login" -H 'Content-Type: application/json' \
  -d '{"email":"driver@company-a.example","password":"another-pass-123"}' -o "$T/l2.json"
check "$(has "$T/l2.json" '"ok":true')" "вход с новым паролем"

curl -s -X POST "$F/api/corp/login" -H 'Content-Type: application/json' \
  -d '{"email":"driver@company-a.example","password":"staff-pass-123"}' -o "$T/l3.json"
check "$(has "$T/l3.json" 'error')" "старый пароль больше не работает"

echo
echo "── Отмена брони ──"
BID=$(cat "$T/nb.json" | "$PY" -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -b "$T/jar" -X POST "$F/api/corp/bookings/$BID/cancel" \
  -H 'Content-Type: application/json' -d '{"reason":""}' -o "$T/cc.json"
check "$(has "$T/cc.json" '"status":"cancelled"')" "бронь отменена"
curl -s -b "$T/jar" -o "$T/me2.json" "$F/api/corp/me"
check "$(has "$T/me2.json" '"activeBookings":0')" "счётчик активных вернулся к нулю"

echo
echo "── Языки ──"
curl -s -b "$T/jar" -c "$T/jar" -o /dev/null "$F/api/corp/lang?to=kk&next=/corp"
curl -s -b "$T/jar" -o "$T/kk.html" "$F/corp"
check "$(has "$T/kk.html" 'Компания кабинеті')" "казахский переключился"

curl -s -b "$T/jar" -c "$T/jar" -o /dev/null "$F/api/corp/lang?to=en&next=/corp"
curl -s -b "$T/jar" -o "$T/en.html" "$F/corp"
check "$(has "$T/en.html" 'Company account')" "английский переключился"

curl -s -b "$T/jar" -o "$T/enb.html" "$F/corp/bookings"
check "$(has "$T/enb.html" 'My bookings')" "страница броней тоже по-английски"

loc=$(curl -s -o /dev/null -w "%{redirect_url}" -b "$T/jar" "$F/api/corp/lang?to=ru&next=https://evil.example/x")
check "$(echo "$loc" | grep -qa 'evil' && echo 0 || echo 1)" "чужой адрес возврата отбит"

echo
echo "── Выход и чужие токены ──"
curl -s -b "$T/jar" -c "$T/jar2" -o /dev/null -X DELETE "$F/api/corp/login"
curl -s -b "$T/jar2" -L -o "$T/out.html" "$F/corp"
# Язык к этому моменту переключён на английский и живёт в отдельной куке,
# которую выход не трогает — и не должен: это настройка, а не сессия.
check "$(has "$T/out.html" 'Corporate portal')" "после выхода снова форма входа"
check "$(grep -qa 'Company account' "$T/out.html" && echo 0 || echo 1)" "кабинет после выхода не отдаётся"

CORP_TOKEN=$(curl -s -X POST "http://127.0.0.1:$BACK_PORT/api/corp/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@company-a.example","password":"corp-pass-12345"}' \
  | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('token',''))")
acode=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $CORP_TOKEN" \
  "http://127.0.0.1:$BACK_PORT/api/admin/rooms")
check "$([ "$acode" = "401" ] && echo 1 || echo 0)" "корп-токен не пускает в админку отеля (получили $acode)"

echo
echo "── Админка компаний ──"
curl -s -c "$T/ajar" -X POST "$F/api/admin/login" -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"live-admin-pass"}' -o "$T/al.json"
check "$(has "$T/al.json" '"ok":true')" "администратор отеля вошёл через фронт"

curl -s -b "$T/ajar" -o "$T/list.html" "$F/admin/kompanii"
check "$(has "$T/list.html" 'Корпоративные клиенты')" "список компаний открылся"
check "$(has "$T/list.html" 'Компания-пример А')" "компания в списке"
check "$(has "$T/list.html" 'Активна')" "видно состояние договора"

curl -s -b "$T/ajar" -o "$T/co.html" "$F/admin/kompanii/company-a"
check "$(has "$T/co.html" 'Реквизиты и договор')" "карточка компании открылась"
check "$(has "$T/co.html" 'Корпоративный прайс')" "раздел прайса на месте"
check "$(has "$T/co.html" 'admin@company-a.example')" "сотрудники подтянулись"
check "$(has "$T/co.html" 'Заявки компании')" "раздел заявок на месте"
check "$(has "$T/co.html" 'driver@company-a.example')" "заведённый в кабинете сотрудник виден и отелю"

acode=$(curl -s -o /dev/null -w "%{http_code}" "$F/admin/kompanii")
check "$([ "$acode" = "307" ] && echo 1 || echo 0)" "без входа админка уводит на форму (получили $acode)"

# Приостановка договора должна немедленно закрывать кабинет — это главный
# рычаг отеля, если компания перестала платить.
curl -s -b "$T/ajar" -X PATCH "$F/api/admin/corp/companies/company-a" \
  -H 'Content-Type: application/json' -d '{"isActive":false}' -o "$T/off.json"
check "$(has "$T/off.json" '"isActive":false')" "договор приостановлен"
ccode=$(curl -s -b "$T/jar" -o /dev/null -w "%{http_code}" "$F/api/corp/me")
check "$([ "$ccode" = "403" ] && echo 1 || echo 0)" "кабинет закрылся сразу (получили $ccode)"

curl -s -b "$T/ajar" -X PATCH "$F/api/admin/corp/companies/company-a" \
  -H 'Content-Type: application/json' -d '{"isActive":true}' -o /dev/null
ccode=$(curl -s -b "$T/jar" -o /dev/null -w "%{http_code}" "$F/api/corp/me")
check "$([ "$ccode" = "200" ] && echo 1 || echo 0)" "и открылся обратно (получили $ccode)"

# Прайс: ставим точечную цену и проверяем, что её видит компания.
cat > "$T/rates.json" <<'JSON'
[{"roomSlug":"comfort","price":31000}]
JSON
curl -s -b "$T/ajar" -X PUT "$F/api/admin/corp/companies/company-a/rates" \
  -H 'Content-Type: application/json' --data-binary @"$T/rates.json" -o "$T/rr.json"
check "$(has "$T/rr.json" '31000')" "цена по договору сохранена"
curl -s -b "$T/jar" -o "$T/rooms.json" "$F/api/corp/rooms"
check "$(has "$T/rooms.json" '"corpPrice":31000')" "компания видит новую цену"

echo
echo "── Финансы и отчёты ──"
# Язык к этому моменту переключён на английский предыдущей секцией. Возвращаем
# русский: заодно проверяем, что переключение работает в обе стороны.
curl -s -b "$T/jar" -c "$T/jar" -o /dev/null "$F/api/corp/lang?to=ru&next=/corp"
curl -s -b "$T/jar" -o "$T/ru.html" "$F/corp"
check "$(has "$T/ru.html" 'Кабинет компании')" "русский вернулся"

curl -s -b "$T/jar" -o "$T/fin.html" "$F/corp/finance"
check "$(has "$T/fin.html" 'Финансы')" "финансы открылись"
check "$(has "$T/fin.html" 'К оплате')" "видна сумма долга"
check "$(has "$T/fin.html" 'Расходы по месяцам')" "разбивка по месяцам на месте"
check "$(has "$T/fin.html" 'постоплата')" "условия оплаты из договора подтянулись"

# Отчёт не считает отменённые заявки, а единственная к этому моменту уже
# отменена — иначе проверяли бы пустой экран и ничего не узнали.
cat > "$T/rep_booking.json" <<JSON
{"checkIn":"$IN","checkOut":"$OUT","adults":1,"items":[{"roomSlug":"standart","roomsCount":1}]}
JSON
curl -s -b "$T/jar" -X POST "$F/api/corp/bookings"   -H 'Content-Type: application/json' --data-binary @"$T/rep_booking.json" -o "$T/rb.json"
check "$(has "$T/rb.json" '"number":"K-')" "для отчёта создана свежая бронь"

curl -s -b "$T/jar" -o "$T/rep.html" "$F/corp/reports"
check "$(has "$T/rep.html" 'Отчёты')" "отчёты открылись"
check "$(has "$T/rep.html" 'Сотрудник')" "разбивка по сотрудникам есть"
check "$(has "$T/rep.html" 'Айгуль')" "в отчёте виден автор брони"
check "$(has "$T/rep.html" 'Итого')" "строка итога посчитана"
check "$(has "$T/rep.html" 'По периодам')" "разбивка по периодам на месте"
check "$(has "$T/rep.html" 'По статусам')" "разбивка по статусам на месте"
check "$(has "$T/rep.html" 'Квартал')" "переключатель периода есть"

# Боковое меню: у ответственного все разделы, у сотрудника — только свои.
check "$(has "$T/cab.html" 'Финансы')" "в меню ответственного есть финансы"
curl -s -b "$T/jar3" -o "$T/cabemp.html" "$F/corp"
check "$(grep -qa 'Финансы' "$T/cabemp.html" && echo 0 || echo 1)" "у сотрудника финансов в меню нет"

# Деньги всей компании рядовому сотруднику не показываем.
curl -s -b "$T/jar3" -L -o "$T/finemp.html" "$F/corp/finance"
check "$(grep -qa 'К оплате' "$T/finemp.html" && echo 0 || echo 1)" "сотруднику финансы закрыты"
curl -s -b "$T/jar3" -L -o "$T/repemp.html" "$F/corp/reports"
check "$(grep -qa 'Итого' "$T/repemp.html" && echo 0 || echo 1)" "сотруднику отчёты закрыты"

echo
echo "── Сверка с образцом заказчика ──"
check "$(has "$T/pick.html" 'Airis Residence')" "чип отеля над панелью поиска"
check "$(has "$T/pick.html" 'Подробнее')" "ссылка «Подробнее» у номера"
check "$(has "$T/pick.html" 'фото')" "бейдж с числом фотографий"
curl -s -b "$T/jar" -o "$T/bk3.html" "$F/corp/bookings"
check "$(has "$T/bk3.html" 'Новое бронирование')" "кнопка «+ Новое бронирование» в истории"

echo
echo "── Публичная страница для компаний ──"
code=$(curl -s -o "$T/pub.html" -w "%{http_code}" "$F/korporativnym-klientam")
check "$([ "$code" = "200" ] && echo 1 || echo 0)" "страница отдаёт 200 (получили $code)"
check "$(has "$T/pub.html" 'Кому это подходит')" "объяснение для кого"
check "$(has "$T/pub.html" 'Как подключиться')" "порядок подключения"
check "$(has "$T/pub.html" '/corp/login')" "кнопка входа в кабинет"
check "$(has "$T/pub.html" 'заявка из кабинета')" "честно сказано про подтверждение менеджером"

curl -s -o "$T/home2.html" "$F/"
check "$(has "$T/home2.html" 'Размещаете сотрудников регулярно')" "блок для компаний на главной"
check "$(has "$T/home2.html" 'korporativnym-klientam')" "ссылка в подвале"
curl -s -o "$T/sm.xml" "$F/sitemap.xml"
check "$(has "$T/sm.xml" 'korporativnym-klientam')" "страница попала в sitemap"

echo
echo "── Публичный сайт и админка не задеты ──"
curl -s -o "$T/home.html" "$F/"
check "$(has "$T/home.html" 'Airis Residence')" "главная жива"
code=$(curl -s -o /dev/null -w "%{http_code}" "$F/admin/login")
check "$([ "$code" = "200" ] && echo 1 || echo 0)" "вход в админку отеля открывается"
code=$(curl -s -o /dev/null -w "%{http_code}" "$F/nomera")
check "$([ "$code" = "200" ] && echo 1 || echo 0)" "страница номеров открывается"

echo
echo "Итог: $ok прошло, $bad провалено"
[ "$bad" = "0" ] || exit 1
