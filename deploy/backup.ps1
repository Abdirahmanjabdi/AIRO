# =============================================================================
# Sentinel Trading — Production Backup Script
# Backs up PostgreSQL data and MinIO model store
# Schedule via Windows Task Scheduler for daily backups
# =============================================================================

param(
    [string]$BackupDir = "C:\Sentinel\Backups",
    [int]$RetainDays = 7
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$backupPath = "$BackupDir\$timestamp"

Write-Host "Sentinel Backup — $timestamp" -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $backupPath | Out-Null

# --- PostgreSQL dump ---
Write-Host "Backing up PostgreSQL..." -ForegroundColor Yellow
$pgContainer = docker compose -f docker-compose.prod.yml ps -q postgres 2>$null
if ($pgContainer) {
    docker exec $pgContainer pg_dumpall -U sentinel > "$backupPath\postgres_full.sql"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  PostgreSQL backup: $backupPath\postgres_full.sql" -ForegroundColor Green
    } else {
        Write-Host "  PostgreSQL backup FAILED" -ForegroundColor Red
    }
} else {
    Write-Host "  PostgreSQL container not running — skipped" -ForegroundColor Yellow
}

# --- Redis dump ---
Write-Host "Backing up Redis..." -ForegroundColor Yellow
$redisContainer = docker compose -f docker-compose.prod.yml ps -q redis 2>$null
if ($redisContainer) {
    docker exec $redisContainer redis-cli BGSAVE 2>$null
    Start-Sleep -Seconds 2
    docker cp "${redisContainer}:/data/dump.rdb" "$backupPath\redis_dump.rdb" 2>$null
    if (Test-Path "$backupPath\redis_dump.rdb") {
        Write-Host "  Redis backup: $backupPath\redis_dump.rdb" -ForegroundColor Green
    } else {
        Write-Host "  Redis backup: no dump.rdb found (may be empty)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Redis container not running — skipped" -ForegroundColor Yellow
}

# --- Compress ---
Write-Host "Compressing backup..." -ForegroundColor Yellow
$archivePath = "$BackupDir\sentinel-backup-$timestamp.zip"
Compress-Archive -Path $backupPath -DestinationPath $archivePath -Force
Remove-Item -Recurse -Force $backupPath
Write-Host "  Archive: $archivePath" -ForegroundColor Green

# --- Cleanup old backups ---
Write-Host "Cleaning up backups older than $RetainDays days..." -ForegroundColor Yellow
$cutoff = (Get-Date).AddDays(-$RetainDays)
Get-ChildItem "$BackupDir\sentinel-backup-*.zip" | Where-Object { $_.LastWriteTime -lt $cutoff } | ForEach-Object {
    Write-Host "  Removing: $($_.Name)" -ForegroundColor Gray
    Remove-Item $_.FullName -Force
}

$totalSize = (Get-ChildItem "$BackupDir\sentinel-backup-*.zip" | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "`nBackup complete. Total backup size: $([math]::Round($totalSize, 1))MB" -ForegroundColor Green
