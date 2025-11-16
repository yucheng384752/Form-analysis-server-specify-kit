# Form Analysis System PowerShell Startup Script
# 設置控制台編碼為 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host ""
Write-Host "========================================"  -ForegroundColor Green
Write-Host "     Form Analysis System Startup"  -ForegroundColor Green  
Write-Host "========================================"  -ForegroundColor Green
Write-Host ""

# Set working directory to project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location $projectRoot

# Check Docker service
Write-Host "[1/5] Checking Docker service status..." -ForegroundColor Yellow
try {
    docker --version | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Docker service is running normally" -ForegroundColor Green
    } else {
        throw "Docker is not running properly"
    }
} catch {
    Write-Host "Docker is not installed or not running" -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}

# Check docker-compose file  
if (!(Test-Path "form-analysis-server\docker-compose.yml")) {
    Write-Host "docker-compose.yml file not found" -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}

Write-Host ""
Write-Host "[2/5] Stopping existing containers..." -ForegroundColor Yellow
Set-Location "form-analysis-server"
docker-compose down --remove-orphans | Out-Null

Write-Host ""
Write-Host "[3/5] Starting PostgreSQL database..." -ForegroundColor Yellow
docker-compose up -d db | Out-Null
Write-Host "Waiting for database (15s)..." -ForegroundColor Cyan
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "[4/5] Starting backend API..." -ForegroundColor Yellow  
docker-compose up -d backend | Out-Null
Write-Host "Waiting for API (20s)..." -ForegroundColor Cyan
Start-Sleep -Seconds 20

Write-Host ""
Write-Host "[5/5] Starting frontend..." -ForegroundColor Yellow
docker-compose up -d frontend | Out-Null
Write-Host "Waiting for frontend (15s)..." -ForegroundColor Cyan
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "========================================"  -ForegroundColor Green
Write-Host "            Startup Complete!"  -ForegroundColor Green
Write-Host "========================================"  -ForegroundColor Green
Write-Host ""

Write-Host "Service Links:" -ForegroundColor White
Write-Host "  Frontend: http://localhost:18003/index.html" -ForegroundColor Cyan
Write-Host "  API Docs: http://localhost:18002/docs" -ForegroundColor Cyan  
Write-Host "  Database: localhost:18001" -ForegroundColor Cyan

Write-Host ""
docker-compose ps
