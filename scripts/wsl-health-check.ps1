<#
.SYNOPSIS
    WSL / Docker Desktop health check and auto-recovery.
    Called automatically by start-dev.bat before launching containers.

.DESCRIPTION
    Checks:
      1. Docker Desktop process is running (starts it if not)
      2. docker-desktop WSL distro is responsive
      3. Docker daemon is reachable

    Recovery levels (lightest to heaviest):
      Level 1 -- wsl --shutdown + wait for restart
      Level 2 -- unregister docker-desktop distro + restart Docker Desktop

    On each recovery attempt a diagnostic snapshot is saved to:
      %LOCALAPPDATA%\Docker\wsl-recovery-logs\recovery-<timestamp>.log

.PARAMETER Quiet
    Suppress non-error output (CI mode).

.PARAMETER MaxAttempts
    Maximum recovery attempts (default 2).

.OUTPUTS
    Exit 0 -- healthy / recovered, safe to start containers
    Exit 1 -- unrecoverable, manual intervention required
#>

param(
    [switch]$Quiet,
    [int]$MaxAttempts = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'SilentlyContinue'

$LogDir        = "$env:LOCALAPPDATA\Docker\wsl-recovery-logs"
$DockerExe     = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
function Write-Step { param([string]$Msg, [string]$Color = 'Cyan')
    if (-not $Quiet) { Write-Host "  [WSL] $Msg" -ForegroundColor $Color } }
function Write-OK   { param([string]$m) Write-Step "OK    $m" 'Green'  }
function Write-Warn { param([string]$m) Write-Step "WARN  $m" 'Yellow' }
function Write-Fail { param([string]$m) Write-Step "FAIL  $m" 'Red'    }

# ---------------------------------------------------------------------------
# Health probes
# ---------------------------------------------------------------------------
function Test-DockerDesktopRunning {
    return ($null -ne (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue))
}

function Get-WslDistroState {
    param([string]$Distro)
    $raw = wsl.exe --list --verbose 2>&1
    foreach ($line in $raw) {
        $clean = ($line -replace '[^\x20-\x7E]', '').Trim()
        if ($clean -match [regex]::Escape($Distro)) {
            if ($clean -match 'Running') { return 'Running' }
            if ($clean -match 'Stopped') { return 'Stopped' }
            return 'Unknown'
        }
    }
    return 'NotFound'
}

function Test-WslDistroAlive {
    param([string]$Distro)
    $out = wsl.exe -d $Distro -- echo alive 2>&1
    return (($out -join '') -match 'alive')
}

function Test-DockerDaemon {
    $null = docker info 2>&1
    return ($LASTEXITCODE -eq 0)
}

function Wait-ForCondition {
    param(
        [scriptblock]$Condition,
        [int]$TimeoutSec  = 60,
        [int]$IntervalSec = 5
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) { return $true }
        if (-not $Quiet) { Write-Host '.' -NoNewline }
        Start-Sleep -Seconds $IntervalSec
    }
    if (-not $Quiet) { Write-Host '' }
    return $false
}

# ---------------------------------------------------------------------------
# Diagnostic snapshot
# ---------------------------------------------------------------------------
function Save-DiagnosticSnapshot {
    param([string]$Reason)
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    }
    $ts      = Get-Date -Format 'yyyyMMdd-HHmmss'
    $logFile = "$LogDir\recovery-$ts.log"

    $buf = [System.Collections.Generic.List[string]]::new()
    $buf.Add("=== WSL Recovery Snapshot: $ts ===")
    $buf.Add("Reason : $Reason")
    $buf.Add("Machine: $env:COMPUTERNAME  User: $env:USERNAME")
    $buf.Add('')

    $buf.Add('--- wsl --list --verbose ---')
    $buf.AddRange([string[]](wsl.exe --list --verbose 2>&1))
    $buf.Add('')

    $backendLog = "$env:LOCALAPPDATA\Docker\log\host\com.docker.backend.exe.log"
    if (Test-Path $backendLog) {
        $buf.Add('--- com.docker.backend.exe.log (last 60 lines) ---')
        $buf.AddRange([string[]](Get-Content $backendLog -Tail 60))
        $buf.Add('')
    }

    $today      = Get-Date -Format 'yyyy-MM-dd'
    $electronLog = "$env:LOCALAPPDATA\Docker\log\host\electron-$today.log"
    if (Test-Path $electronLog) {
        $errLines = Select-String -Path $electronLog `
            -Pattern 'error|bootstrap|fail' -CaseSensitive:$false |
            Select-Object -Last 30 | ForEach-Object { $_.Line }
        if ($errLines) {
            $buf.Add("--- electron-$today.log (error lines) ---")
            $buf.AddRange([string[]]$errLines)
            $buf.Add('')
        }
    }

    $buf | Out-File -FilePath $logFile -Encoding UTF8
    return $logFile
}

# ---------------------------------------------------------------------------
# Recovery procedures
# ---------------------------------------------------------------------------
function Invoke-SoftRecovery {
    # Level 1: wsl --shutdown so Docker Desktop can re-bootstrap the distro
    Write-Warn 'Level-1 recovery: running wsl --shutdown ...'
    $snap = Save-DiagnosticSnapshot 'docker-desktop distro unresponsive (soft reset)'
    Write-Step "Diagnostic snapshot: $snap"

    wsl.exe --shutdown 2>&1 | Out-Null
    Write-Step 'WSL shut down. Waiting 5s ...'
    Start-Sleep -Seconds 5
}

function Invoke-HardRecovery {
    # Level 2: unregister docker-desktop (keeps docker-desktop-data: images/volumes safe)
    #          then restart Docker Desktop to let it recreate the distro
    Write-Warn 'Level-2 recovery: unregistering docker-desktop distro ...'
    $snap = Save-DiagnosticSnapshot 'docker-desktop distro unrecoverable (hard reset)'
    Write-Step "Diagnostic snapshot: $snap"

    wsl.exe --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 3

    Write-Warn 'Unregistering docker-desktop (images/volumes in docker-desktop-data are preserved) ...'
    wsl.exe --unregister docker-desktop 2>&1 | Out-Null
    Start-Sleep -Seconds 2

    if (-not (Test-Path $DockerExe)) {
        Write-Fail "Docker Desktop executable not found: $DockerExe"
        Write-Fail 'Please start Docker Desktop manually and retry.'
        return $false
    }

    Write-Step 'Starting Docker Desktop ...'
    Start-Process $DockerExe

    Write-Step 'Waiting for Docker Desktop to initialise (up to 90s) ...'
    if (-not $Quiet) { Write-Host -NoNewline '  [WSL] ' }
    return (Wait-ForCondition -Condition { Test-DockerDaemon } -TimeoutSec 90 -IntervalSec 5)
}

function Start-DockerDesktopAndWait {
    if (-not (Test-Path $DockerExe)) {
        Write-Fail "Docker Desktop not found: $DockerExe"
        return $false
    }
    Write-Step 'Docker Desktop is not running. Starting it ...'
    Start-Process $DockerExe
    Write-Step 'Waiting for Docker Desktop to initialise (up to 90s) ...'
    if (-not $Quiet) { Write-Host -NoNewline '  [WSL] ' }
    return (Wait-ForCondition -Condition { Test-DockerDaemon } -TimeoutSec 90 -IntervalSec 5)
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if (-not $Quiet) {
    Write-Host ''
    Write-Host '  -- WSL Health Check -----------------------------------' -ForegroundColor DarkCyan
}

# 1. Is Docker Desktop running?
if (-not (Test-DockerDesktopRunning)) {
    Write-Warn 'Docker Desktop is not running.'
    if (-not (Start-DockerDesktopAndWait)) {
        Write-Fail 'Docker Desktop failed to start within timeout.'
        Write-Fail 'Please launch Docker Desktop manually and retry.'
        exit 1
    }
    Write-OK 'Docker Desktop started.'
    if (-not $Quiet) {
        Write-Host '  -------------------------------------------------------' -ForegroundColor DarkCyan
        Write-Host ''
    }
    exit 0
}

# 2. docker-desktop distro state
$state = Get-WslDistroState 'docker-desktop'
Write-Step "docker-desktop distro state: $state"

if ($state -eq 'NotFound') {
    Write-Warn 'docker-desktop distro not found. Triggering Docker Desktop to recreate it ...'
    $ok = Invoke-HardRecovery
    if (-not $ok) {
        Write-Fail 'Could not recreate docker-desktop distro. Reinstalling Docker Desktop may be required.'
        exit 1
    }
    Write-OK 'docker-desktop distro recreated.'
    if (-not $Quiet) {
        Write-Host '  -------------------------------------------------------' -ForegroundColor DarkCyan
        Write-Host ''
    }
    exit 0
}

# 3. Distro alive + daemon reachable -> all good
$alive = Test-WslDistroAlive 'docker-desktop'
if ($alive -and (Test-DockerDaemon)) {
    Write-OK 'WSL distro responsive. Docker daemon reachable.'
    if (-not $Quiet) {
        Write-Host '  -------------------------------------------------------' -ForegroundColor DarkCyan
        Write-Host ''
    }
    exit 0
}

# 4. Distro alive but daemon not yet ready (Docker Desktop still starting up)
if ($alive -and -not (Test-DockerDaemon)) {
    Write-Step 'Distro OK, waiting for Docker daemon (up to 30s) ...'
    if (-not $Quiet) { Write-Host -NoNewline '  [WSL] ' }
    $ok = Wait-ForCondition -Condition { Test-DockerDaemon } -TimeoutSec 30 -IntervalSec 5
    if ($ok) {
        Write-OK 'Docker daemon is ready.'
        if (-not $Quiet) {
            Write-Host '  -------------------------------------------------------' -ForegroundColor DarkCyan
            Write-Host ''
        }
        exit 0
    }
    # Daemon still not ready after 30s -> fall through to recovery
}

# 5. Recovery loop
$recovered = $false
for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    Write-Host ''
    Write-Warn "Recovery attempt $attempt of $MaxAttempts ..."

    if ($attempt -eq 1) {
        Invoke-SoftRecovery
        Write-Step 'Waiting for daemon after soft reset (up to 45s) ...'
        if (-not $Quiet) { Write-Host -NoNewline '  [WSL] ' }
        $ok = Wait-ForCondition -Condition {
            (Test-WslDistroAlive 'docker-desktop') -and (Test-DockerDaemon)
        } -TimeoutSec 45 -IntervalSec 5
    } else {
        $ok = Invoke-HardRecovery
    }

    if ($ok) {
        Write-OK "Recovered on attempt $attempt."
        $recovered = $true
        break
    }
}

if ($recovered) {
    if (-not $Quiet) {
        Write-Host '  -------------------------------------------------------' -ForegroundColor DarkCyan
        Write-Host ''
    }
    exit 0
}

# 6. All attempts exhausted
Write-Host ''
Write-Fail "WSL recovery failed after $MaxAttempts attempt(s)."
Write-Host ''
Write-Host '  Manual recovery steps:' -ForegroundColor Yellow
Write-Host '    1. wsl --shutdown' -ForegroundColor Yellow
Write-Host '    2. Restart Docker Desktop from the Start Menu' -ForegroundColor Yellow
Write-Host '    3. If still failing: wsl --unregister docker-desktop' -ForegroundColor Yellow
Write-Host ''
Write-Host "  Diagnostic logs: $LogDir" -ForegroundColor DarkGray
Write-Host ''
exit 1
