param(
    [string]$ApiBase = "http://localhost:18002",
    [string]$TenantId,
    [string]$FilePath
)

# Test Import V2 Commit Flow (P2)

$faRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
if (-not $FilePath) {
    $FilePath = Join-Path $faRoot "test_p2.csv"
}

Write-Host "Testing Import V2 Commit Flow (P2)..." -ForegroundColor Cyan

# 0. Get Tenant
Write-Host "0. Getting Tenant..."
if (-not $TenantId) {
    $tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get
    if (-not $tenants) {
        Write-Host "Error: No tenants found" -ForegroundColor Red
        exit 1
    }
    $tenants = @($tenants)
    $TenantId = $tenants[0].id
}
Write-Host "Using Tenant ID: $TenantId"

# 1. Create Import Job
Write-Host "1. Creating Import Job (P2)..."
$response = & curl.exe -sS -f -X POST "$ApiBase/api/v2/import/jobs" `
    -H "X-Tenant-Id: $TenantId" `
  -F "table_code=P2" `
    -F "allow_duplicate=true" `
    -F "files=@$FilePath" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to create import job" -ForegroundColor Red
    Write-Host $response
    exit 1
}

try {
    $job = $response | ConvertFrom-Json
} catch {
    Write-Host "Error: Create job response is not valid JSON" -ForegroundColor Red
    Write-Host $response
    exit 1
}

$jobId = $job.id
Write-Host "Job Created: $jobId"

# 2. Poll Status until READY
Write-Host "2. Polling Status (Wait for READY)..."
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $job = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$TenantId" }
    Write-Host "Current Status: $($job.status)"

    if ($job.status -eq "READY") {
        Write-Host "Job is READY!" -ForegroundColor Green
        break
    }
    if ($job.status -eq "FAILED") {
        Write-Host "Error: Job FAILED" -ForegroundColor Red
        $job | ConvertTo-Json -Depth 10 | Write-Host
        exit 1
    }
}

if ($job.status -ne "READY") {
    Write-Host "Error: Job did not become READY" -ForegroundColor Red
    $job | ConvertTo-Json -Depth 10 | Write-Host
    exit 1
}

# 3. Commit Job
Write-Host "3. Committing Job..."
$job = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId/commit" -Method Post -Headers @{ "X-Tenant-Id" = "$TenantId" }
Write-Host "Commit Triggered. Status: $($job.status)"

# 4. Poll Status until COMPLETED
Write-Host "4. Polling Status (Wait for COMPLETED)..."
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $job = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$TenantId" }
    Write-Host "Current Status: $($job.status)"

    if ($job.status -eq "COMPLETED") {
        Write-Host "Success: Job is COMPLETED!" -ForegroundColor Green
        break
    }
    if ($job.status -eq "FAILED") {
        Write-Host "Error: Job FAILED" -ForegroundColor Red
        $job | ConvertTo-Json -Depth 10 | Write-Host
        exit 1
    }
}

if ($job.status -ne "COMPLETED") {
    Write-Host "Timeout: Job did not become COMPLETED in time." -ForegroundColor Yellow
    $job | ConvertTo-Json -Depth 10 | Write-Host
}
