$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $projectRoot "backend"
$frontend = Join-Path $projectRoot "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
$envFile = Join-Path $backend ".env"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Local environment not found. Run .\setup-local.ps1 first."
}

if (-not (Test-Path -LiteralPath (Join-Path $frontend "node_modules"))) {
    throw "Frontend packages not found. Run .\setup-local.ps1 first."
}

$apiKeyLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^MISTRAL_API_KEYS?=' } | Select-Object -First 1
if (-not $apiKeyLine -or $apiKeyLine -match '^MISTRAL_API_KEYS?=$') {
    Write-Warning "No Mistral API key is configured. The UI will open, but extraction remains disabled until a key is set and the backend is restarted."
}

$backendCommand = "Set-Location -LiteralPath '$backend'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000"
$frontendCommand = "Set-Location -LiteralPath '$frontend'; npm.cmd start"

Start-Process powershell.exe -ArgumentList @('-NoExit', '-Command', $backendCommand)
Start-Process powershell.exe -ArgumentList @('-NoExit', '-Command', $frontendCommand)

Write-Host "Backend: http://localhost:8000/api/docs" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:4200" -ForegroundColor Cyan
