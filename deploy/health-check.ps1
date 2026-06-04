# =============================================================================
# Sentinel Trading — Production Health Check
# Run periodically or after deployment to verify all systems are operational
# =============================================================================

param(
    [string]$BaseUrl = "http://localhost"
)

$ErrorActionPreference = "Continue"

Write-Host "`nSentinel Health Check — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "=" * 60

$allGood = $true

# --- Docker services ---
Write-Host "`n[Docker Services]" -ForegroundColor Yellow
$services = @("brain", "frontend", "postgres", "redis", "minio")
foreach ($svc in $services) {
    $status = docker compose -f docker-compose.prod.yml ps --format json 2>$null | ConvertFrom-Json | Where-Object { $_.Service -eq $svc }
    if ($status) {
        $health = if ($status.Health) { $status.Health } else { $status.State }
        $color = if ($health -eq "healthy" -or $health -eq "running") { "Green" } else { "Red"; $allGood = $false }
        Write-Host "  $($svc.PadRight(12)) $health" -ForegroundColor $color
    } else {
        Write-Host "  $($svc.PadRight(12)) NOT RUNNING" -ForegroundColor Red
        $allGood = $false
    }
}

# --- API endpoints ---
Write-Host "`n[API Endpoints]" -ForegroundColor Yellow

$endpoints = @(
    @{ Path = "/healthz";  Name = "Liveness" },
    @{ Path = "/readyz";   Name = "Readiness" }
)

foreach ($ep in $endpoints) {
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $resp = Invoke-RestMethod -Uri "$BaseUrl$($ep.Path)" -TimeoutSec 10
        $sw.Stop()
        $status = $resp.status
        $color = if ($status -eq "ok" -or $status -eq "ready") { "Green" } else { "Yellow"; $allGood = $false }
        Write-Host "  $($ep.Name.PadRight(12)) $status ($($sw.ElapsedMilliseconds)ms)" -ForegroundColor $color

        if ($resp.details -and $resp.details.PSObject.Properties.Count -gt 0) {
            $resp.details.PSObject.Properties | ForEach-Object {
                Write-Host "    $($_.Name): $($_.Value)" -ForegroundColor Yellow
                $allGood = $false
            }
        }
    } catch {
        Write-Host "  $($ep.Name.PadRight(12)) FAILED ($($_.Exception.Message))" -ForegroundColor Red
        $allGood = $false
    }
}

# --- Readiness details ---
Write-Host "`n[Subsystem Status]" -ForegroundColor Yellow
try {
    $ready = Invoke-RestMethod -Uri "$BaseUrl/readyz" -TimeoutSec 10
    $checks = @(
        @{ Name = "ML Model";    Ok = $ready.model_loaded },
        @{ Name = "Redis";       Ok = $ready.redis_connected },
        @{ Name = "PostgreSQL";  Ok = $ready.db_connected },
        @{ Name = "Vault";       Ok = ($ready.vault_connected -or -not $ready.vault_required) }
    )
    foreach ($check in $checks) {
        $color = if ($check.Ok) { "Green" } else { "Red"; $allGood = $false }
        $symbol = if ($check.Ok) { "OK" } else { "FAIL" }
        Write-Host "  $($check.Name.PadRight(12)) $symbol" -ForegroundColor $color
    }
} catch {
    Write-Host "  Could not fetch readiness details" -ForegroundColor Red
    $allGood = $false
}

# --- Bridge relay ---
Write-Host "`n[Bridge Relay]" -ForegroundColor Yellow
$bridgeSvc = Get-Service -Name "SentinelBridgeRelay" -ErrorAction SilentlyContinue
if ($bridgeSvc) {
    $color = if ($bridgeSvc.Status -eq "Running") { "Green" } else { "Red"; $allGood = $false }
    Write-Host "  Service:     $($bridgeSvc.Status)" -ForegroundColor $color
} else {
    Write-Host "  Service:     Not installed (run install-bridge-service.ps1)" -ForegroundColor Yellow
}

# --- Disk space ---
Write-Host "`n[Disk Space]" -ForegroundColor Yellow
$disk = Get-PSDrive C
$freeGB = [math]::Round($disk.Free / 1GB, 1)
$color = if ($freeGB -gt 10) { "Green" } elseif ($freeGB -gt 5) { "Yellow" } else { "Red"; $allGood = $false }
Write-Host "  C: drive:    ${freeGB}GB free" -ForegroundColor $color

# --- Docker disk ---
$dockerDisk = docker system df --format "table {{.Type}}\t{{.Size}}\t{{.Reclaimable}}" 2>$null
if ($dockerDisk) {
    Write-Host "`n[Docker Disk Usage]" -ForegroundColor Yellow
    $dockerDisk | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
}

# --- Summary ---
Write-Host "`n" + ("=" * 60)
if ($allGood) {
    Write-Host "  ALL SYSTEMS OPERATIONAL" -ForegroundColor Green
} else {
    Write-Host "  ISSUES DETECTED — review above" -ForegroundColor Red
}
Write-Host ""
