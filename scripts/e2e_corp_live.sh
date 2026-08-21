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
