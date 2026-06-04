# =============================================================================
# Sentinel Trading — EC2 Windows Server Bootstrap
# Run ONCE on a fresh EC2 Windows Server 2022 instance to install prerequisites
# Then run ec2-deploy.ps1 to deploy the application
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  EC2 Windows Server Bootstrap" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# --- Install Chocolatey ---
Write-Host "[1/5] Installing Chocolatey package manager..." -ForegroundColor Yellow
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:PATH = "$env:PATH;$env:ProgramData\chocolatey\bin"
    Write-Host "  Chocolatey installed" -ForegroundColor Green
} else {
    Write-Host "  Chocolatey already installed" -ForegroundColor Green
}

# --- Install Docker Desktop ---
Write-Host "`n[2/5] Installing Docker Desktop..." -ForegroundColor Yellow
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    choco install docker-desktop -y --no-progress
    Write-Host "  Docker Desktop installed. RESTART REQUIRED before running ec2-deploy.ps1" -ForegroundColor Red
    $needsRestart = $true
} else {
    Write-Host "  Docker already installed: $(docker --version)" -ForegroundColor Green
}

# --- Install Python 3.12 ---
Write-Host "`n[3/5] Installing Python 3.12..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    choco install python312 -y --no-progress
    $env:PATH = "$env:PATH;$env:ProgramFiles\Python312;$env:ProgramFiles\Python312\Scripts"
    Write-Host "  Python installed" -ForegroundColor Green
} else {
    Write-Host "  Python already installed: $(python --version)" -ForegroundColor Green
}

# --- Install Git ---
Write-Host "`n[4/5] Installing Git..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    choco install git -y --no-progress
    Write-Host "  Git installed" -ForegroundColor Green
} else {
    Write-Host "  Git already installed: $(git --version)" -ForegroundColor Green
}

# --- Install NSSM (for Windows Service management) ---
Write-Host "`n[5/5] Installing NSSM..." -ForegroundColor Yellow
if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    choco install nssm -y --no-progress
    Write-Host "  NSSM installed" -ForegroundColor Green
} else {
    Write-Host "  NSSM already installed" -ForegroundColor Green
}

# --- Open firewall ports ---
Write-Host "`nConfiguring firewall..." -ForegroundColor Yellow
$rules = @(
    @{ Name = "Sentinel HTTP";   Port = 80;   Protocol = "TCP" },
    @{ Name = "Sentinel HTTPS";  Port = 443;  Protocol = "TCP" },
    @{ Name = "MinIO Console";   Port = 9001; Protocol = "TCP" }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -LocalPort $rule.Port -Protocol $rule.Protocol -Action Allow | Out-Null
        Write-Host "  Opened port $($rule.Port) ($($rule.Name))" -ForegroundColor Green
    } else {
        Write-Host "  Port $($rule.Port) already open ($($rule.Name))" -ForegroundColor Green
    }
}

# --- Summary ---
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Bootstrap Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($needsRestart) {
    Write-Host "`n  ACTION REQUIRED: Restart this instance for Docker to work." -ForegroundColor Red
    Write-Host "  After restart, run:" -ForegroundColor Yellow
} else {
    Write-Host "`n  Next steps:" -ForegroundColor Yellow
}

Write-Host "  1. Clone the repo:   git clone <your-repo-url> C:\Sentinel\App" -ForegroundColor White
Write-Host "  2. Copy env:         cp .env.production .env" -ForegroundColor White
Write-Host "  3. Edit secrets:     notepad .env" -ForegroundColor White
Write-Host "  4. Deploy:           .\deploy\ec2-deploy.ps1" -ForegroundColor White
Write-Host ""
