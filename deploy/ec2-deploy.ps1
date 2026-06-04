# =============================================================================
# Sentinel Trading — EC2 Windows Server Deployment Script
# Run this on a fresh EC2 Windows Server 2022 instance with Docker Desktop
# =============================================================================

param(
    [switch]$SkipBuild,
    [switch]$SkipBridge,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Sentinel Trading — EC2 Deployment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# --- Step 1: Verify prerequisites ---
Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Yellow

$missing = @()
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { $missing += "Docker" }
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    if (-not (docker compose version 2>$null)) { $missing += "docker-compose" }
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $missing += "Python" }

if ($missing.Count -gt 0) {
    Write-Host "  MISSING: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "  Install Docker Desktop and Python 3.12+ before running this script." -ForegroundColor Red
    exit 1
}

Write-Host "  Docker: $(docker --version)" -ForegroundColor Green
Write-Host "  Python: $(python --version)" -ForegroundColor Green

# --- Step 2: Verify .env file ---
Write-Host "`n[2/7] Checking environment configuration..." -ForegroundColor Yellow

if (-not (Test-Path $EnvFile)) {
    if (Test-Path ".env.production") {
        Copy-Item ".env.production" $EnvFile
        Write-Host "  Copied .env.production to .env" -ForegroundColor Yellow
        Write-Host "  EDIT .env NOW with your actual secrets and IP, then re-run this script." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "  No .env file found. Copy .env.production to .env and fill in values." -ForegroundColor Red
        exit 1
    }
}

$envContent = Get-Content $EnvFile -Raw
if ($envContent -match "CHANGE_ME") {
    Write-Host "  .env still contains CHANGE_ME placeholders. Edit it first." -ForegroundColor Red
    exit 1
}
if ($envContent -match "YOUR_EC2_PUBLIC_IP") {
    Write-Host "  .env still contains YOUR_EC2_PUBLIC_IP. Set your actual IP/domain." -ForegroundColor Red
    exit 1
}

Write-Host "  .env loaded successfully" -ForegroundColor Green

# --- Step 3: Generate secrets if needed ---
Write-Host "`n[3/7] Validating security keys..." -ForegroundColor Yellow

$keyCheck = python -c "
import os
for var in ['SENTINEL_SECRET_KEY', 'SENTINEL_ENCRYPTION_KEY', 'POSTGRES_PASSWORD']:
    val = ''
    with open('.env') as f:
        for line in f:
            if line.strip().startswith(var + '='):
                val = line.strip().split('=', 1)[1]
    if not val or 'CHANGE_ME' in val:
        print(f'MISSING: {var}')
" 2>&1

if ($keyCheck) {
    Write-Host "  $keyCheck" -ForegroundColor Red
    exit 1
}
Write-Host "  All required secrets are set" -ForegroundColor Green

# --- Step 4: Build containers ---
Write-Host "`n[4/7] Building Docker containers..." -ForegroundColor Yellow

if (-not $SkipBuild) {
    docker compose -f docker-compose.prod.yml --env-file $EnvFile build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Docker build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Build complete" -ForegroundColor Green
} else {
    Write-Host "  Skipped (--SkipBuild)" -ForegroundColor Yellow
}

# --- Step 5: Start services ---
Write-Host "`n[5/7] Starting services..." -ForegroundColor Yellow

docker compose -f docker-compose.prod.yml --env-file $EnvFile up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Failed to start services!" -ForegroundColor Red
    exit 1
}

Write-Host "  Waiting for services to become healthy..." -ForegroundColor Yellow
$maxWait = 120
$elapsed = 0
while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 5
    $elapsed += 5

    $brainHealth = docker compose -f docker-compose.prod.yml ps --format json 2>$null | ConvertFrom-Json | Where-Object { $_.Service -eq "brain" }
    if ($brainHealth.Health -eq "healthy") {
        Write-Host "  Brain API is healthy!" -ForegroundColor Green
        break
    }
    Write-Host "  Waiting... ($elapsed`s / $maxWait`s)" -ForegroundColor Gray
}

if ($elapsed -ge $maxWait) {
    Write-Host "  Brain API did not become healthy within ${maxWait}s. Check logs:" -ForegroundColor Red
    Write-Host "  docker compose -f docker-compose.prod.yml logs brain" -ForegroundColor Yellow
}

# --- Step 6: Verify endpoints ---
Write-Host "`n[6/7] Verifying endpoints..." -ForegroundColor Yellow

try {
    $health = Invoke-RestMethod -Uri "http://localhost/healthz" -TimeoutSec 10
    Write-Host "  /healthz: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "  /healthz: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $ready = Invoke-RestMethod -Uri "http://localhost/readyz" -TimeoutSec 10
    Write-Host "  /readyz: $($ready.status)" -ForegroundColor Green
    if ($ready.details) {
        $ready.details.PSObject.Properties | ForEach-Object {
            Write-Host "    $($_.Name): $($_.Value)" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "  /readyz: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

# --- Step 7: Install and start Bridge Relay ---
Write-Host "`n[7/7] MT5 Bridge Relay..." -ForegroundColor Yellow

if (-not $SkipBridge) {
    if (-not (Test-Path "venv")) {
        Write-Host "  Creating Python virtual environment..." -ForegroundColor Yellow
        python -m venv venv
    }

    Write-Host "  Installing Python dependencies..." -ForegroundColor Yellow
    & venv\Scripts\pip.exe install -q -e ".[dev]" 2>$null

    $bridgeEnv = @{
        "BRAIN_API_URL"     = "http://localhost:8000"
        "REDIS_URL"         = "redis://localhost:6379/0"
        "SENTINEL_USER_ID"  = ""
        "SENTINEL_ENFORCE_MODE" = "false"
    }

    Write-Host "  Bridge relay is ready to start. Run it with:" -ForegroundColor Green
    Write-Host "  .\venv\Scripts\python.exe -m sentinel.bridge.mt5_relay" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Or install as a Windows Service with:" -ForegroundColor Green
    Write-Host "  .\deploy\install-bridge-service.ps1" -ForegroundColor Cyan
} else {
    Write-Host "  Skipped (--SkipBridge)" -ForegroundColor Yellow
}

# --- Summary ---
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:     http://localhost" -ForegroundColor White
Write-Host "  Brain API:    http://localhost/v1/" -ForegroundColor White
Write-Host "  MinIO Console: http://localhost:9001" -ForegroundColor White
Write-Host ""
Write-Host "  Logs:  docker compose -f docker-compose.prod.yml logs -f" -ForegroundColor Gray
Write-Host "  Stop:  docker compose -f docker-compose.prod.yml down" -ForegroundColor Gray
Write-Host ""
