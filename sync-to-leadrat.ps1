$ErrorActionPreference = "Stop"
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = "C:\Leadrat AI\pdf-intelligence-app"

if (-not (Test-Path -LiteralPath $target)) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
}

robocopy $source $target /E /XD .git .venv node_modules dist data __pycache__ .pytest_cache .angular /XF *.pyc
$copyCode = $LASTEXITCODE
if ($copyCode -gt 7) {
    throw "Project sync failed with robocopy exit code $copyCode."
}

Write-Host "Updated project synced to $target" -ForegroundColor Green
