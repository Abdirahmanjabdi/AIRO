# =============================================================================
# Install Sentinel Bridge Relay as a Windows Service using NSSM
# Prerequisites: NSSM (https://nssm.cc) must be on PATH
# =============================================================================

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$ServiceName = "SentinelBridgeRelay"
$PythonExe = (Resolve-Path "venv\Scripts\python.exe").Path
$ProjectRoot = (Get-Location).Path

Write-Host "Installing $ServiceName as Windows Service..." -ForegroundColor Cyan

# Check NSSM
if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "NSSM not found. Install from https://nssm.cc or use:" -ForegroundColor Red
    Write-Host '  choco install nssm' -ForegroundColor Yellow
    exit 1
}

# Check if service already exists
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Service already exists (Status: $($existing.Status)). Removing..." -ForegroundColor Yellow
    nssm stop $ServiceName 2>$null
    nssm remove $ServiceName confirm
}

# Install service
nssm install $ServiceName $PythonExe "-m" "sentinel.bridge.mt5_relay"
nssm set $ServiceName AppDirectory $ProjectRoot
nssm set $ServiceName AppStdout "$ProjectRoot\logs\bridge-stdout.log"
nssm set $ServiceName AppStderr "$ProjectRoot\logs\bridge-stderr.log"
nssm set $ServiceName AppRotateFiles 1
nssm set $ServiceName AppRotateBytes 10485760

# Environment variables
nssm set $ServiceName AppEnvironmentExtra `
    "BRAIN_API_URL=http://localhost:8000" `
    "REDIS_URL=redis://localhost:6379/0" `
    "SENTINEL_ENFORCE_MODE=false" `
    "PYTHONUNBUFFERED=1"

# Auto-restart on failure
nssm set $ServiceName AppRestartDelay 5000
nssm set $ServiceName Start SERVICE_AUTO_START

# Create logs directory
New-Item -ItemType Directory -Force -Path "$ProjectRoot\logs" | Out-Null

Write-Host "Service installed. Starting..." -ForegroundColor Green
nssm start $ServiceName

$svc = Get-Service -Name $ServiceName
Write-Host "Service Status: $($svc.Status)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commands:" -ForegroundColor Gray
Write-Host "  nssm status $ServiceName       # Check status" -ForegroundColor Gray
Write-Host "  nssm restart $ServiceName      # Restart" -ForegroundColor Gray
Write-Host "  nssm stop $ServiceName         # Stop" -ForegroundColor Gray
Write-Host "  nssm remove $ServiceName       # Uninstall" -ForegroundColor Gray
Write-Host "  Get-Content logs\bridge-stdout.log -Tail 50  # View logs" -ForegroundColor Gray
