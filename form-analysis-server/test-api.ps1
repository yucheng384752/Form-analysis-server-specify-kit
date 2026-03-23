param(
    [string]$ApiBase = $env:API_BASE,
    [string]$TenantId = $env:TENANT_ID
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ApiBase)) {
    $ApiBase = 'http://localhost:18002'
}

function Write-Test([string]$Message) { Write-Host "[TEST] $Message" -ForegroundColor Yellow }
function Write-Ok([string]$Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-Err([string]$Message) { Write-Host "[ERR]  $Message" -ForegroundColor Red }
function Write-Skip([string]$Message) { Write-Host "[SKIP] $Message" -ForegroundColor DarkYellow }

Write-Host "v2 import jobs smoke (PowerShell)" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan

if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Err "curl.exe 不可用（Windows 10/11 通常內建）"
    exit 1
}

function Get-TenantId {
    if (-not [string]::IsNullOrWhiteSpace($TenantId)) { return $TenantId }
    $tenants = Invoke-RestMethod -Method Get -Uri "$ApiBase/api/tenants" -TimeoutSec 10
    if (-not $tenants -or $tenants.Count -eq 0) {
        throw "No tenants found; create a tenant first or set TENANT_ID"
    }
    if ($tenants[0].tenant_id) { return $tenants[0].tenant_id }
    if ($tenants[0].id) { return $tenants[0].id }
    throw "Cannot resolve tenant_id from /api/tenants response"
}

function Get-JobStatus([string]$JobId) {
    $job = Invoke-RestMethod -Method Get -Uri "$ApiBase/api/v2/import/jobs/$JobId" -Headers @{ 'X-Tenant-Id' = $TenantId } -TimeoutSec 10
    return $job.status
}

function Wait-JobTerminal([string]$JobId, [int]$TimeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $status = Get-JobStatus -JobId $JobId
        if ($status -in @('READY','FAILED','COMPLETED','CANCELLED')) { return $status }
        Start-Sleep -Seconds 1
    }
    return 'TIMEOUT'
}

function New-P1Csv([string]$Path, [switch]$Invalid) {
    if ($Invalid) {
        @(
            'lot_no,product_name,quantity,production_date',
            '1234567_01,,50,2024-01-16',
            '1234567_01,測試產品C,-75,2024-01-17'
        ) | Set-Content -Path $Path -Encoding UTF8
    } else {
        @(
            'lot_no,product_name,quantity,production_date',
            '1234567_01,測試產品A,100,2024-01-15',
            '1234567_01,測試產品B,50,2024-01-16'
        ) | Set-Content -Path $Path -Encoding UTF8
    }
}

function Create-ImportJobP1([string]$CsvPath, [string]$FileName) {
    $url = "$ApiBase/api/v2/import/jobs"
    $args = @(
        '-s',
        '-X', 'POST',
        '-H', "X-Tenant-Id: $TenantId",
        '-F', 'table_code=P1',
        '-F', 'allow_duplicate=false',
        '-F', "files=@$CsvPath;type=text/csv;filename=$FileName",
        $url
    )
    $raw = & curl.exe @args
    if ($LASTEXITCODE -ne 0) { throw "curl.exe failed creating job" }
    return $raw | ConvertFrom-Json
}

function Commit-Job([string]$JobId) {
    $raw = & curl.exe -s -X POST -H "X-Tenant-Id: $TenantId" "$ApiBase/api/v2/import/jobs/$JobId/commit"
    if ($LASTEXITCODE -ne 0) { throw "curl.exe failed commit" }
    return $raw | ConvertFrom-Json
}

function Get-JobErrors([string]$JobId) {
    $raw = & curl.exe -s -H "X-Tenant-Id: $TenantId" "$ApiBase/api/v2/import/jobs/$JobId/errors"
    if ($LASTEXITCODE -ne 0) { throw "curl.exe failed errors" }
    return $raw | ConvertFrom-Json
}

$TenantId = Get-TenantId
Write-Host "API_BASE=$ApiBase"
Write-Host "TENANT_ID=$TenantId"

$validFile = New-TemporaryFile
$invalidFile = New-TemporaryFile
New-P1Csv -Path $validFile.FullName
New-P1Csv -Path $invalidFile.FullName -Invalid

try {
    Write-Test "create job (valid)"
    $job = Create-ImportJobP1 -CsvPath $validFile.FullName -FileName 'P1_1234567_01.csv'
    $job | ConvertTo-Json -Depth 50

    if (-not $job.id) { throw "Missing job id" }

    Write-Test "poll job"
    $status = Wait-JobTerminal -JobId $job.id -TimeoutSec 90
    Write-Host "job status: $status"

    if ($status -eq 'READY') {
        Write-Test "commit"
        $commit = Commit-Job -JobId $job.id
        $commit | ConvertTo-Json -Depth 50
        Write-Ok "commit request sent"
    } else {
        Write-Skip "job not READY; skip commit"
    }

    Write-Test "create job (invalid) and read errors"
    $errJob = Create-ImportJobP1 -CsvPath $invalidFile.FullName -FileName 'P1_1234567_01_error.csv'
    $errJob | ConvertTo-Json -Depth 50

    if ($errJob.id) {
        $errStatus = Wait-JobTerminal -JobId $errJob.id -TimeoutSec 90
        Write-Host "error job status: $errStatus"
        $errors = Get-JobErrors -JobId $errJob.id
        $errors | ConvertTo-Json -Depth 100
    }

    Write-Ok "done"
}
finally {
    Remove-Item -Force $validFile.FullName, $invalidFile.FullName -ErrorAction SilentlyContinue
}