# Test Import V2 Commit Flow

$ApiBase = "http://localhost:18002"

# 為了避免後端「Duplicate file detected」檢查（通常以檔名為準），
# 這裡會把來源檔複製到 TEMP 並用唯一檔名上傳。
$candidateFiles = @(
    (Join-Path $env:USERPROFILE "Desktop\侑特資料\新侑特資料\P3_0902_P24 copy.csv"),
    (Join-Path $PSScriptRoot "uploads/_import_test_P3_0902_P24_copy.csv"),
    (Join-Path $PSScriptRoot "test-results/test_p3.csv"),
    (Join-Path $PSScriptRoot "test_p3.csv")
)

$sourceFile = $candidateFiles | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $sourceFile) {
    Write-Host "Error: No P3 sample file found. Tried:" -ForegroundColor Red
    $candidateFiles | ForEach-Object { Write-Host " - $_" }
    exit 1
}

$ts = Get-Date -Format "yyyyMMddHHmmss"
$tempUploadFile = Join-Path $env:TEMP "_import_test_P3_commit_$ts.csv"
Copy-Item -Path $sourceFile -Destination $tempUploadFile -Force
# 後端可能以 file_hash 判斷重複檔案；追加空白行可避免 hash 相同，且多數 CSV 解析會忽略尾端空行。
Add-Content -Path $tempUploadFile -Value "" -Encoding UTF8
$File = $tempUploadFile

Write-Host "Testing Import V2 Commit Flow..." -ForegroundColor Cyan

# 0. Get Tenant
Write-Host "0. Getting Tenant..."
$tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get
if (-not $tenants) {
    Write-Host "Error: No tenants found" -ForegroundColor Red
    exit 1
}
$tenants = @($tenants)
$tenantId = $tenants[0].id
Write-Host "Using Tenant ID: $tenantId"

# 1. Create Import Job
Write-Host "1. Creating Import Job (P3)..."
$response = & curl.exe -sS -X POST "$ApiBase/api/v2/import/jobs" `
    -H "X-Tenant-Id: $tenantId" `
    -F "table_code=P3" `
    -F "files=@$File" `
    -w "`nHTTP_STATUS:%{http_code}`n" 2>&1

$httpStatus = ($response | Select-String -Pattern '^HTTP_STATUS:(\d+)$' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1)
if (-not $httpStatus) {
        Write-Host "Error: Failed to determine HTTP status" -ForegroundColor Red
        Write-Host $response
        exit 1
}
if ([int]$httpStatus -lt 200 -or [int]$httpStatus -ge 300) {
        Write-Host "Error: Failed to create import job (HTTP $httpStatus)" -ForegroundColor Red
        Write-Host $response
        exit 1
}

try {
    $jsonText = ($response -split "`r?`nHTTP_STATUS:\d+`r?`n")[0]
    $job = $jsonText | ConvertFrom-Json
} catch {
        Write-Host "Error: Create job response is not valid JSON" -ForegroundColor Red
        Write-Host $response
        exit 1
}
$jobId = $job.id
Write-Host "Job Created: $jobId"

# 2. Poll Status until READY
Write-Host "2. Polling Status (Wait for READY)..."
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    $job = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$tenantId" }
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
$job = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId/commit" -Method Post -Headers @{ "X-Tenant-Id" = "$tenantId" }
Write-Host "Commit Triggered. Status: $($job.status)"

# 4. Poll Status until COMPLETED
Write-Host "4. Polling Status (Wait for COMPLETED)..."
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    $job = Invoke-RestMethod -Uri "$ApiBase/api/v2/import/jobs/$jobId" -Method Get -Headers @{ "X-Tenant-Id" = "$tenantId" }
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

if ($tempUploadFile -and (Test-Path $tempUploadFile)) {
    Remove-Item $tempUploadFile -ErrorAction SilentlyContinue
}
