$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location (Join-Path $projectRoot "backend")
try {
    & ".\.venv\Scripts\python.exe" -m pytest -q
}
finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm.cmd test -- --watch=false
    npm.cmd run build
}
finally {
    Pop-Location
}

