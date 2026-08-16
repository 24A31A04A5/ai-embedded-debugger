$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Starting local infrastructure (PostgreSQL 16 + MinIO)..."
docker compose up -d

Write-Host ""
Write-Host "Waiting for PostgreSQL..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    docker compose exec -T postgres pg_isready -U aed -d aed 2>$null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $ready) {
    Write-Error "PostgreSQL did not become ready in time."
}

Write-Host "Local infrastructure is ready."
Write-Host "  PostgreSQL: localhost:5432"
Write-Host "  MinIO API:  http://localhost:9000"
Write-Host "  MinIO UI:   http://localhost:9001"
