# Test Import V2 Commit Flow

$ApiBase = "http://localhost:18002"
$File = "test_p3.csv"

Write-Host "Testing Import V2 Commit Flow..." -ForegroundColor Cyan

# 0. Get Tenant
Write-Host "0. Getting Tenant..."
$tenantsResponse = curl.exe -s "$ApiBase/api/tenants"
$tenants = $tenantsResponse | ConvertFrom-Json
if ($tenants.Count -eq 0) {
    Write-Host "Error: No tenants found" -ForegroundColor Red
    exit 1
}
$tenantId = $tenants[0].id
Write-Host "Using Tenant ID: $tenantId"

# 1. Create Import Job
Write-Host "1. Creating Import Job (P3)..."
$response = curl.exe -s -X POST "$ApiBase/api/v2/import/jobs" `
  -H "X-Tenant-Id: $tenantId" `
  -F "table_code=P3" `
  -F "files=@$File"

$job = $response | ConvertFrom-Json
$jobId = $job.id
Write-Host "Job Created: $jobId"

# 2. Poll Status until READY
Write-Host "2. Polling Status (Wait for READY)..."
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    $response = curl.exe -s "$ApiBase/api/v2/import/jobs/$jobId" -H "X-Tenant-Id: $tenantId"
    $job = $response | ConvertFrom-Json
    Write-Host "Current Status: $($job.status)"
    
    if ($job.status -eq "READY") {
        Write-Host "Job is READY!" -ForegroundColor Green
        break
    }
}

if ($job.status -ne "READY") {
    Write-Host "Error: Job did not become READY" -ForegroundColor Red
    exit 1
}

# 3. Commit Job
Write-Host "3. Committing Job..."
$response = curl.exe -s -X POST "$ApiBase/api/v2/import/jobs/$jobId/commit" -H "X-Tenant-Id: $tenantId"
$job = $response | ConvertFrom-Json
Write-Host "Commit Triggered. Status: $($job.status)"

# 4. Poll Status until COMPLETED
Write-Host "4. Polling Status (Wait for COMPLETED)..."
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    $response = curl.exe -s "$ApiBase/api/v2/import/jobs/$jobId" -H "X-Tenant-Id: $tenantId"
    $job = $response | ConvertFrom-Json
    Write-Host "Current Status: $($job.status)"
    
    if ($job.status -eq "COMPLETED") {
        Write-Host "Success: Job is COMPLETED!" -ForegroundColor Green
        break
    }
    if ($job.status -eq "FAILED") {
        Write-Host "Error: Job FAILED" -ForegroundColor Red
        Write-Host "Error Summary: $($job.error_summary | ConvertTo-Json)"
        exit 1
    }
}

if ($job.status -ne "COMPLETED") {
    Write-Host "Timeout: Job did not become COMPLETED in time." -ForegroundColor Yellow
}
