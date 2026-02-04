<#
Form Analysis System PowerShell Startup Script

Goals:
- Work from any current directory (always use the compose folder)
- Support Docker Compose v2 (docker compose) and v1 (docker-compose)
- Fail fast with helpful logs if backend/frontend fails to start
#>

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding
} catch {
    # best-effort
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "     Form Analysis System Startup" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
$serverPath = Join-Path $projectRoot "form-analysis-server"

function Resolve-Compose {
    try {
        docker compose version | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $script:ComposeCommand = "docker"
            $script:ComposeBaseArgs = @("compose")
            return
        }
    } catch {
        # ignore
    }

    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $script:ComposeCommand = "docker-compose"
        $script:ComposeBaseArgs = @()
        return
    }

    throw "Docker Compose not found. Install Docker Desktop (compose plugin) or docker-compose.";
}

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ComposeArgs,
        [switch]$ShowOutput
    )

    if ($ShowOutput) {
        & $script:ComposeCommand @($script:ComposeBaseArgs + $ComposeArgs)
    } else {
        & $script:ComposeCommand @($script:ComposeBaseArgs + $ComposeArgs) *> $null
    }
    return $LASTEXITCODE
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Default
    )

    if (-not (Test-Path $Path)) {
        return $Default
    }

    foreach ($line in (Get-Content $Path -ErrorAction SilentlyContinue)) {
        $trim = ("$line").Trim()
        if ($trim -eq "" -or $trim.StartsWith("#")) { continue }

        $m = [regex]::Match($trim, "^" + [regex]::Escape($Key) + "\s*=\s*(.*)$")
        if ($m.Success) {
            $val = $m.Groups[1].Value.Trim()
            if ($val.StartsWith('"') -and $val.EndsWith('"')) {
                $val = $val.Substring(1, $val.Length - 2)
            }
            return $val
        }
    }

    return $Default
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $useCurl = [bool](Get-Command curl.exe -ErrorAction SilentlyContinue)

    while ((Get-Date) -lt $deadline) {
        try {
            if ($useCurl) {
                curl.exe -f $Url -o $null -s 2>$null
                if ($LASTEXITCODE -eq 0) { return $true }
            } else {
                $r = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -ErrorAction SilentlyContinue
                if ($null -ne $r -and $r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
            }
        } catch {}

        Start-Sleep -Seconds 2
    }

    return $false
}

# [1/6] Check Docker
Write-Host "[1/6] Checking Docker service status..." -ForegroundColor Yellow
try {
    docker --version | Out-Null
    docker info | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker not ready" }
    Write-Host "Docker service is running normally" -ForegroundColor Green
} catch {
    Write-Host "Docker is not installed or not running. Please start Docker Desktop." -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}

# [2/6] Locate compose folder
if (-not (Test-Path (Join-Path $serverPath "docker-compose.yml"))) {
    Write-Host "docker-compose.yml file not found: $serverPath" -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}

Set-Location $serverPath

# Ensure .env exists for variable substitution
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    try {
        Copy-Item ".env.example" ".env" -Force
        Write-Host "[2/6] Created .env from .env.example" -ForegroundColor Cyan
    } catch {
        Write-Host "[2/6] Warning: failed to create .env; falling back to environment variables" -ForegroundColor Yellow
    }
}

try {
    Resolve-Compose
} catch {
    Write-Host "[ERROR] $_" -ForegroundColor Red
    Read-Host "Press Enter to continue"
    exit 1
}

$apiPort = Get-DotEnvValue -Path (Join-Path $serverPath ".env") -Key "HOST_API_PORT" -Default "18002"
$frontendPort = Get-DotEnvValue -Path (Join-Path $serverPath ".env") -Key "FRONTEND_PORT" -Default "18003"
$dbPort = Get-DotEnvValue -Path (Join-Path $serverPath ".env") -Key "POSTGRES_PORT" -Default "18001"

Write-Host "";
Write-Host "[3/6] Stopping existing containers..." -ForegroundColor Yellow
$null = Invoke-Compose @("down", "--remove-orphans")

Write-Host "";
Write-Host "[4/6] Starting PostgreSQL database..." -ForegroundColor Yellow
if ((Invoke-Compose @("up", "-d", "db")) -ne 0) {
    Write-Host "Database failed to start" -ForegroundColor Red
    Invoke-Compose @("logs", "--tail=80", "db") -ShowOutput
    exit 1
}

Write-Host "Waiting for database to be ready..." -ForegroundColor Cyan
$dbReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $dbReadyExit = Invoke-Compose @("exec", "-T", "db", "pg_isready", "-U", "app") 2>$null
        if ($dbReadyExit -eq 0) { $dbReady = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}

if (-not $dbReady) {
    Write-Host "Database readiness timed out" -ForegroundColor Red
    Invoke-Compose @("logs", "--tail=120", "db") -ShowOutput
    exit 1
}

Write-Host "";
Write-Host "[5/6] Starting backend API..." -ForegroundColor Yellow
if ((Invoke-Compose @("up", "-d", "--build", "backend")) -ne 0) {
    Write-Host "Backend failed to start" -ForegroundColor Red
    Invoke-Compose @("logs", "--tail=120", "backend") -ShowOutput
    exit 1
}

Write-Host "Waiting for API healthz..." -ForegroundColor Cyan
if (-not (Wait-HttpOk -Url "http://localhost:$apiPort/healthz" -TimeoutSeconds 90)) {
    Write-Host "API did not become ready" -ForegroundColor Red
    Invoke-Compose @("logs", "--tail=160", "backend") -ShowOutput
    exit 1
}

Write-Host "";
Write-Host "[6/6] Starting frontend..." -ForegroundColor Yellow
if ((Invoke-Compose @("up", "-d", "--build", "frontend")) -ne 0) {
    Write-Host "Frontend failed to start" -ForegroundColor Red
    Invoke-Compose @("logs", "--tail=160", "frontend") -ShowOutput
    exit 1
}

Write-Host "Ensuring frontend dependencies (node_modules) are installed..." -ForegroundColor Cyan
try {
    docker exec form_analysis_frontend sh -lc "test -d node_modules/recharts || npm ci --silent" | Out-Null
    $null = Invoke-Compose @("restart", "frontend")
} catch {
    Write-Host "Warning: failed to ensure frontend dependencies; check frontend logs if startup fails" -ForegroundColor Yellow
}

Write-Host "Waiting for frontend..." -ForegroundColor Cyan
if (-not (Wait-HttpOk -Url "http://localhost:$frontendPort" -TimeoutSeconds 90)) {
    Write-Host "Frontend did not become ready" -ForegroundColor Red
    Invoke-Compose @("logs", "--tail=200", "frontend") -ShowOutput
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "            Startup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Service Links:" -ForegroundColor White
Write-Host "  Frontend: http://localhost:$frontendPort/index.html" -ForegroundColor Cyan
Write-Host "  API Docs: http://localhost:$apiPort/docs" -ForegroundColor Cyan
Write-Host "  Database: localhost:$dbPort" -ForegroundColor Cyan

Write-Host ""
Invoke-Compose @("ps") -ShowOutput
