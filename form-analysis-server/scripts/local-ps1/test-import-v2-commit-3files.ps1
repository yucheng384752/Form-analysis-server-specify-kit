param(
    [string]$ApiBase = "http://localhost:18002",
    [string]$ApiKey,
    [string]$ApiKeyHeader = "X-API-Key",
    [string]$AdminApiKey,
    [string]$AdminApiKeyHeader = "X-Admin-API-Key",
    [string]$DataDir,
    [string]$P1File,
    [string]$P2File,
    [string]$P3File
)

# Import V2: run P1/P2/P3 with the provided 3 CSV files

$faRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
$LocalDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $DataDir) { $DataDir = $env:UT_DATA_DIR }
if (-not $DataDir) { throw "DataDir is required. Set -DataDir or env:UT_DATA_DIR" }

if (-not $P1File) { $P1File = Join-Path $DataDir "P1_2507173_02.csv" }
if (-not $P2File) { $P2File = Join-Path $DataDir "P2_2507173_02.csv" }
if (-not $P3File) { $P3File = Join-Path $DataDir "P3_0902_P24 copy.csv" }

function Get-AdminApiKey {
    if ($AdminApiKey) { return $AdminApiKey }

    $fromEnv = $env:ADMIN_API_KEYS
    if ($fromEnv) {
        $first = ($fromEnv -split "," | Select-Object -First 1).Trim()
        if ($first) { return $first }
    }

    $envFile = Join-Path $faRoot ".env"
    if (Test-Path $envFile) {
        $line = (Select-String -Path $envFile -Pattern "^ADMIN_API_KEYS=" | Select-Object -First 1)
        if ($line -and $line.Line) {
            $value = ($line.Line -replace "^ADMIN_API_KEYS=", "").Trim()
            if ($value) {
                $first = ($value -split "," | Select-Object -First 1).Trim()
                if ($first) { return $first }
            }
        }
    }

    return $null
}

function Ensure-ApiKey([string]$tenantId) {
    if ($ApiKey) { return $ApiKey }

    $adminKey = Get-AdminApiKey
    if (-not $adminKey) {
        throw "Missing API key. Provide -ApiKey, or provide -AdminApiKey (or set ADMIN_API_KEYS / .env ADMIN_API_KEYS) so the script can issue a tenant API key."
    }

    $resp = Invoke-RestMethod -Uri "$ApiBase/api/auth/admin/tenant-api-keys" -Method Post `
        -Headers @{ ($AdminApiKeyHeader) = $adminKey } `
        -ContentType "application/json" `
        -Body (@{ tenant_id = $tenantId } | ConvertTo-Json)

    $raw = ($resp.api_key | Out-String).Trim()
    if (-not $raw) { throw "Failed to issue tenant API key via admin endpoint." }
    $ApiKey = $raw
    return $ApiKey
}

function Get-TenantId {
    $headers = @{}
    if ($ApiKey) {
        $headers[$ApiKeyHeader] = $ApiKey
    } else {
        $adminKey = Get-AdminApiKey
        if ($adminKey) {
            $headers[$AdminApiKeyHeader] = $adminKey
        }
    }

    $tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get -Headers $headers
    if (-not $tenants) {
        throw "No tenants found"
    }
    $tenants = @($tenants)
    return $tenants[0].id
}

function Run-ImportCommit([string]$tableCode, [string]$filePath, [string]$tenantId, [string]$apiKeyToUse) {
    Write-Host "--- $tableCode $filePath" -ForegroundColor Cyan

    $resp = & curl.exe -sS -f -X POST "$ApiBase/api/v2/import/jobs" `
        -H "${ApiKeyHeader}: $apiKeyToUse" `
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
        $j = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$tenantId"; "$ApiKeyHeader" = "$apiKeyToUse" }
        if ($j.status -eq "READY") {
            break
        }
        if ($j.status -eq "FAILED") {
            Write-Host "Job FAILED" -ForegroundColor Red
            $j | ConvertTo-Json -Depth 10 | Write-Host
            return $jobId
        }
    }

    $j = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId/commit" -Method Post -Headers @{ "X-Tenant-Id" = "$tenantId"; "$ApiKeyHeader" = "$apiKeyToUse" }

    # wait COMPLETED
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        $j = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$tenantId"; "$ApiKeyHeader" = "$apiKeyToUse" }
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
$apiKeyToUse = Ensure-ApiKey $tenantId
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

Run-ImportCommit "P1" $dstP1 $tenantId $apiKeyToUse | Out-Null
Run-ImportCommit "P2" $dstP2 $tenantId $apiKeyToUse | Out-Null
Run-ImportCommit "P3" $dstP3 $tenantId $apiKeyToUse | Out-Null
