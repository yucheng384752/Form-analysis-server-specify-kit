param(
    [string]$ApiBase = "http://localhost:18002",
    [string]$P1File = "c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P1_2507173_02.csv",
    [string]$P2File = "c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P2_2507173_02.csv",
    [string]$P3File = "c:\Users\yucheng\Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv"
)

# Import V2: run P1/P2/P3 with the provided 3 CSV files

$faRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
$LocalDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-TenantId {
    $tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get
    if (-not $tenants) {
        throw "No tenants found"
    }
    $tenants = @($tenants)
    return $tenants[0].id
}

function Run-ImportCommit([string]$tableCode, [string]$filePath, [string]$tenantId) {
    Write-Host "--- $tableCode $filePath" -ForegroundColor Cyan

    $resp = & curl.exe -sS -f -X POST "$ApiBase/api/v2/import/jobs" `
        -H "X-Tenant-Id: $tenantId" `
        -F "table_code=$tableCode" `
        -F "allow_duplicate=true" `
        -F "files=@$filePath" 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Create job failed" -ForegroundColor Red
        Write-Host $resp
        return $null
    }

    try {
        $job = $resp | ConvertFrom-Json
    } catch {
        Write-Host "Create job response is not valid JSON" -ForegroundColor Red
        Write-Host $resp
        return $null
    }

    $jobId = $job.id
    Write-Host "Job Created: $jobId"

    # wait READY
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        $j = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$tenantId" }
        if ($j.status -eq "READY") {
            break
        }
        if ($j.status -eq "FAILED") {
            Write-Host "Job FAILED" -ForegroundColor Red
            $j | ConvertTo-Json -Depth 10 | Write-Host
            return $jobId
        }
    }

    $j = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId/commit" -Method Post -Headers @{ "X-Tenant-Id" = "$tenantId" }

    # wait COMPLETED
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        $j = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$tenantId" }
        if ($j.status -eq "COMPLETED") {
            Write-Host "COMPLETED" -ForegroundColor Green
            return $jobId
        }
        if ($j.status -eq "FAILED") {
            Write-Host "Job FAILED" -ForegroundColor Red
            $j | ConvertTo-Json -Depth 10 | Write-Host
            return $jobId
        }
    }

    Write-Host "TIMEOUT" -ForegroundColor Yellow
    return $jobId
}

$tenantId = Get-TenantId
Write-Host "Using Tenant ID: $tenantId" -ForegroundColor Gray

$srcP1 = $P1File
$srcP2 = $P2File
$srcP3 = $P3File

# 若外部資料夾不存在，改用 repo 內 uploads 的本地複本（先前測試可能已建立）
if (-not (Test-Path $srcP1)) {
    $fallback = Join-Path $faRoot "uploads/_import_test_P1_2507173_02.csv"
    if (Test-Path $fallback) { $srcP1 = $fallback }
}
if (-not (Test-Path $srcP2)) {
    $fallback = Join-Path $faRoot "uploads/_import_test_P2_2507173_02.csv"
    if (Test-Path $fallback) { $srcP2 = $fallback }
}
if (-not (Test-Path $srcP3)) {
    $fallback = Join-Path $faRoot "uploads/_import_test_P3_0902_P24_copy.csv"
    if (Test-Path $fallback) { $srcP3 = $fallback }
}

$dstP1 = Join-Path $LocalDir "_import_test_P1_2507173_02.csv"
$dstP2 = Join-Path $LocalDir "_import_test_P2_2507173_02.csv"
$dstP3 = Join-Path $LocalDir "_import_test_P3_0902_P24_copy.csv"

Copy-Item -LiteralPath $srcP1 -Destination $dstP1 -Force
Copy-Item -LiteralPath $srcP2 -Destination $dstP2 -Force
Copy-Item -LiteralPath $srcP3 -Destination $dstP3 -Force

Run-ImportCommit "P1" $dstP1 $tenantId | Out-Null
Run-ImportCommit "P2" $dstP2 $tenantId | Out-Null
Run-ImportCommit "P3" $dstP3 $tenantId | Out-Null
