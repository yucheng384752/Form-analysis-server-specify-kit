# Test Import V2 Batch Rules & Deduplication

$ApiBase = "http://localhost:18002"
$FileCSV = Join-Path $PSScriptRoot "test-results/test_p3.csv"
if (-not (Test-Path $FileCSV)) {
    $FileCSV = Join-Path $PSScriptRoot "test_p3.csv"
}

$FileTXT = Join-Path $PSScriptRoot "test-results/test_dummy.txt"
try {
    "dummy" | Set-Content -Path $FileTXT -Encoding UTF8
} catch {
    # ignore
}

Write-Host "Testing Import V2 Batch Rules & Deduplication..." -ForegroundColor Cyan

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

# Test 1: Mixed Extensions
Write-Host "`nTest 1: Mixed Extensions (CSV + TXT)..."
try {
    # Note: curl -F allows multiple files.
    # We expect 400 Bad Request
    $response = curl.exe -s -w "%{http_code}" -X POST "$ApiBase/api/v2/import/jobs" `
      -H "X-Tenant-Id: $tenantId" `
      -F "table_code=P3" `
      -F "files=@$FileCSV" `
      -F "files=@$FileTXT"
    
    $httpCode = $response.Substring($response.Length - 3)
    $body = $response.Substring(0, $response.Length - 3)
    
    if ($httpCode -eq "400") {
        Write-Host "Success: Rejected mixed extensions (400)" -ForegroundColor Green
        Write-Host "Response: $body"
    } else {
        Write-Host "Failed: Expected 400, got $httpCode" -ForegroundColor Red
        Write-Host "Response: $body"
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

# Test 2: Duplicate File
Write-Host "`nTest 2: Duplicate File..."
# First upload (should succeed if not already there, or fail if already there from previous tests)
# We'll try to upload test_p3.csv again. It was uploaded in previous commit test.
# So we expect it to fail immediately if the previous test succeeded and committed.
# Wait, ImportFile is created when Job is created. Even if Job is not committed, ImportFile exists?
# Yes, ImportFile is created in `create_import_job`.
# So if we run this script after `test-import-v2-commit.ps1`, it should fail.

$response = curl.exe -s -w "%{http_code}" -X POST "$ApiBase/api/v2/import/jobs" `
  -H "X-Tenant-Id: $tenantId" `
  -F "table_code=P3" `
  -F "files=@$FileCSV"

$httpCode = $response.Substring($response.Length - 3)
$body = $response.Substring(0, $response.Length - 3)

if ($httpCode -eq "400") {
    Write-Host "Success: Rejected duplicate file (400)" -ForegroundColor Green
    Write-Host "Response: $body"
} else {
    # If it succeeded (200), it means the file wasn't in DB?
    # But we just ran commit test which uploaded test_p3.csv.
    # Let's check the response body to be sure.
    Write-Host "Failed: Expected 400 (Duplicate), got $httpCode" -ForegroundColor Red
    Write-Host "Response: $body"
}
