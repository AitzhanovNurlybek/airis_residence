# Запуск сайта на своём компьютере — для проверки шахматки и ИИ-консьержа.
#
# Открывает два окна: бэкенд (база, консьерж) и фронтенд (сам сайт).
# Закрывать их не надо, пока работаете. Когда закончите — просто закройте окна.
#
# Как запустить: правой кнопкой по файлу → «Выполнить с помощью PowerShell».
# Если Windows ругается на запуск скриптов, откройте PowerShell в этой папке и
# выполните:  powershell -ExecutionPolicy Bypass -File .\ЗАПУСТИТЬ.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  Airis Residence — запуск на своём компьютере" -ForegroundColor Cyan
Write-Host "  ───────────────────────────────────────────" -ForegroundColor DarkGray

# Порты 8000 и 3000 могли остаться занятыми от прошлого запуска. Если их не
# освободить, второй запуск молча поднимется на другом порту, и консьерж
# перестанет находить справку об отеле — он ищет её строго на 3000.
foreach ($port in 8000, 3000) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        Write-Host "  Освобождаю порт $port (остался от прошлого запуска)" -ForegroundColor DarkYellow
        $busy | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Milliseconds 700
    }
}

$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "  Не нашёл backend\.venv — сначала поставьте зависимости бэкенда." -ForegroundColor Red
    Read-Host "  Enter — закрыть"
    exit 1
}

Write-Host "  Запускаю бэкенд (база и консьерж)…"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\backend'; Write-Host 'БЭКЕНД — не закрывать' -ForegroundColor Green; & '$python' -m uvicorn app.main:app --port 8000 --reload"
)

Write-Host "  Запускаю сайт…"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\frontend'; `$env:BACKEND_URL='http://127.0.0.1:8000'; Write-Host 'САЙТ — не закрывать' -ForegroundColor Green; npm run dev"
)

Write-Host "  Жду, пока поднимутся…" -NoNewline
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000/admin/login" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { break }
    } catch { }
}
Write-Host ""

$login = ""
$envFile = Join-Path $root "backend\.env"
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^ADMIN_USERNAME=' -ErrorAction SilentlyContinue
    if ($line) { $login = ($line.Line -split '=', 2)[1].Trim().Trim('"') }
}

Write-Host ""
Write-Host "  Готово." -ForegroundColor Green
Write-Host ""
Write-Host "  Сайт:      http://localhost:3000"
Write-Host "  Админка:   http://localhost:3000/admin/login"
if ($login) { Write-Host "  Логин:     $login   (пароль — в backend\.env, строка ADMIN_PASSWORD)" }
Write-Host "  Шахматка:  http://localhost:3000/admin/shahmatka" -ForegroundColor Cyan
Write-Host ""
Write-Host "  На странице шахматки: сверху календарь занятости и форма" -ForegroundColor DarkGray
Write-Host "  «поставить бронь руками», снизу — переписка с консьержем." -ForegroundColor DarkGray
Write-Host ""

Start-Process "http://localhost:3000/admin/shahmatka"
Read-Host "  Enter — закрыть это окно (сайт продолжит работать)"
