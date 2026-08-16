$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Checking local development configuration..."
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Error ".env not found. Copy .env.example to .env and set DATABASE_URL to your Neon PostgreSQL URL."
}

$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch '^\s*DATABASE_URL\s*=\s*.+' -or $envContent -match '^\s*DATABASE_URL\s*=\s*$') {
    Write-Error "DATABASE_URL is not set in .env. Add your Neon PostgreSQL connection string."
}

Write-Host "Configuration looks ready."
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. pip install -e `".[dev]`""
Write-Host "  2. alembic -c db/alembic.ini upgrade head"
Write-Host "  3. uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000"
