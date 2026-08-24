# Полный прогон всех проверок.
#
# Поднимает бэкенд и сайт, прогоняет все наборы тестов, гасит за собой.
# Занимает несколько минут: часть проверок разговаривает с моделью и с Exely,
# то есть уходит наружу и стоит денег.
#
# Как запустить: правой кнопкой → «Выполнить с помощью PowerShell», или
#   powershell -ExecutionPolicy Bypass -File .\ПРОВЕРИТЬ.ps1
#
# Флаги:
#   -Fast    только быстрые проверки, без обращений к модели (секунды, бесплатно)

param([switch]$Fast)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "  Не нашёл backend\.venv" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  Airis Residence — прогон проверок" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────" -ForegroundColor DarkGray

# Старые процессы на портах ломают прогон незаметно: тесты стучатся в 3000, а
# там отвечает сборка недельной давности с прежними ценами. Такое уже было —
# консьерж «называл верную цену», и она была верной для той старой сборки.
foreach ($port in 8000, 3000, 8010) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        Write-Host "  Освобождаю порт $port" -ForegroundColor DarkYellow
        $busy | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    }
}
Start-Sleep -Milliseconds 800

$backend = Start-Process -PassThru -WindowStyle Hidden powershell -ArgumentList @(
    "-Command", "Set-Location '$root\backend'; & '$python' -m uvicorn app.main:app --port 8000 --log-level warning"
)
$frontend = Start-Process -PassThru -WindowStyle Hidden powershell -ArgumentList @(
    "-Command", "Set-Location '$root\frontend'; `$env:BACKEND_URL='http://127.0.0.1:8000'; npx next start --port 3000"
)

Write-Host "  Жду, пока поднимутся…" -NoNewline
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:3000/api/knowledge" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
Write-Host ""

if (-not $ready) {
    Write-Host "  Сайт не поднялся. Соберите его: cd frontend; npm run build" -ForegroundColor Red
    $backend, $frontend | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}

$results = @()

function Run-Suite($title, $script, $arguments) {
    Write-Host ""
    Write-Host "  ▸ $title" -ForegroundColor Cyan
    Push-Location "$root\backend"
    $output = & $python $script @arguments 2>&1 | Out-String
    Pop-Location
    $tail = ($output -split "`n" | Where-Object { $_ -match "Итог|прошло|из \d+|проверки прошли" } | Select-Object -Last 2) -join " "
    $ok = $LASTEXITCODE -eq 0
    Write-Host ("    " + $tail.Trim()) -ForegroundColor $(if ($ok) { "Green" } else { "Red" })
    if (-not $ok) {
        ($output -split "`n" | Where-Object { $_ -match "✗|❌|не прошло|·" } | Select-Object -Last 12) |
            ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    }
    $script:results += [pscustomobject]@{ Проверка = $title; Прошло = $ok }
}

Run-Suite "Общий QA (быстрый, без модели)" "e2e_qa.py" @("http://127.0.0.1:3000")

if (-not $Fast) {
    Run-Suite "Консьерж и справка" "e2e_concierge.py" @("http://127.0.0.1:3000")
    Run-Suite "Платёжные документы" "e2e_payment.py" @("http://127.0.0.1:3000")
    Write-Host ""
    Write-Host "  ▸ Живые диалоги с гостем" -ForegroundColor Cyan
    Write-Host "    (пропущены: стоят около сорока обращений к модели)" -ForegroundColor DarkGray
    Write-Host "    Запустить вручную: cd backend; .venv\Scripts\python.exe e2e_dialog.py" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  ▸ Кабинет компаний и публичный сайт" -ForegroundColor Cyan

# Этот набор написан на shell и требует bash из Git for Windows. В обычной
# консоли PowerShell его нет в PATH, поэтому ищем по известным местам.
#
# Если не нашли — набор помечается пропущенным, а не пройденным. Первая версия
# считала «bash не найден» успехом: в итоге отчёт показывал зелёную галочку
# там, где проверка вообще не запускалась. Молчаливое «всё хорошо» опаснее
# честного «не проверено».
$bash = (Get-Command bash -ErrorAction SilentlyContinue).Source
if (-not $bash) {
    $bash = @(
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files (x86)\Git\bin\bash.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $bash) {
    Write-Host "    пропущено: не нашёл bash.exe (нужен Git for Windows)" -ForegroundColor Yellow
    $results += [pscustomobject]@{ Проверка = "Кабинет и сайт"; Прошло = $null }
} else {
    Push-Location $root
    $live = & $bash "scripts/e2e_corp_live.sh" 2>&1 | Out-String
    Pop-Location
    $liveTail = ($live -split "`n" | Where-Object { $_ -match "Итог:" } | Select-Object -Last 1)
    # Успехом считаем только явный отчёт «0 провалено». Отсутствие отчёта —
    # это сбой запуска, а не тишина довольного теста.
    $liveOk = ($null -ne $liveTail) -and ($liveTail -match "0 провалено")
    if ($liveTail) {
        Write-Host ("    " + $liveTail.Trim()) -ForegroundColor $(if ($liveOk) { "Green" } else { "Red" })
    } else {
        Write-Host "    набор не отчитался — похоже, не запустился" -ForegroundColor Red
        ($live -split "`n" | Select-Object -Last 6) | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
    }
    $results += [pscustomobject]@{ Проверка = "Кабинет и сайт"; Прошло = $liveOk }
}

Write-Host ""
Write-Host "  ─── Итог ───" -ForegroundColor Cyan
$results | ForEach-Object {
    if ($null -eq $_.Прошло) {
        Write-Host ("    ? {0} — не проверялось" -f $_.Проверка) -ForegroundColor Yellow
    } elseif ($_.Прошло) {
        Write-Host ("    ✓ {0}" -f $_.Проверка) -ForegroundColor Green
    } else {
        Write-Host ("    ✗ {0}" -f $_.Проверка) -ForegroundColor Red
    }
}
$bad = ($results | Where-Object { $_.Прошло -eq $false }).Count
$skipped = ($results | Where-Object { $null -eq $_.Прошло }).Count

$backend, $frontend | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
foreach ($port in 8000, 3000) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
if ($bad -eq 0 -and $skipped -eq 0) {
    Write-Host "  Всё прошло." -ForegroundColor Green
} elseif ($bad -eq 0) {
    Write-Host "  Прошло, но $skipped набор(а) не проверялось." -ForegroundColor Yellow
} else {
    Write-Host "  Провалено наборов: $bad" -ForegroundColor Red
}
Write-Host ""
if ([Environment]::UserInteractive -and -not $env:CI) {
    try { Read-Host "  Enter — закрыть" } catch { }
}
exit $bad
