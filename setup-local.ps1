$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $projectRoot "backend"
$frontend = Join-Path $projectRoot "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

Write-Host "Setting up PDF Intelligence..." -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $venvPython)) {
    Push-Location $backend
    try {
        python -m venv .venv
    }
    finally {
        Pop-Location
    }
}

Push-Location $backend
try {
    & $venvPython -m pip install -r requirements-dev.txt
}
finally {
    Pop-Location
}

Push-Location $frontend
try {
    npm.cmd install
}
finally {
    Pop-Location
}

Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next: edit backend\.env and set MISTRAL_API_KEY, then run .\start-local.ps1"

