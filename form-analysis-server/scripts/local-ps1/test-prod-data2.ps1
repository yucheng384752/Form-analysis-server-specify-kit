# Import Production Data Test Script
# Usage: powershell -ExecutionPolicy Bypass -File .\test-prod-data.ps1

param(
    [string]$BaseUrl = "http://localhost:18002",
    [string]$TenantId,
    [string]$DataDir = "C:\Users\yucheng\Desktop\侑特資料\新侑特資料",
    [int]$Take = 3
)

$ErrorActionPreference = "Stop"

if (-not $TenantId) {
    $tenants = Invoke-RestMethod -Uri "$BaseUrl/api/tenants" -Method Get
    $tenants = @($tenants)
    if (-not $tenants -or $tenants.Count -eq 0) {
        throw "No tenants found"
    }
    $TenantId = $tenants[0].id
}

Write-Host "=== Production Data Import Test ===" -ForegroundColor Cyan
Write-Host "Using Tenant ID: $TenantId" -ForegroundColor Green

# Base paths
$basePath = $DataDir
$P1Dir = Join-Path $basePath "P1"
$P2Dir = Join-Path $basePath "P2"

# Function to import a file
function Import-File {
    param(
        [string]$FilePath,
        [string]$TableCode,
        [string]$TenantId
    )
    
    $fileName = Split-Path $FilePath -Leaf
    Write-Host "`n--- Processing: $fileName" -ForegroundColor Cyan
    
    # 1. Create job
    $jobResponse = curl.exe -s -X POST "$BaseUrl/api/v2/import/jobs" `
        -H "X-Tenant-Id: $TenantId" `
        -F "table_code=$TableCode" `
        -F "allow_duplicate=true" `
        -F "files=@$FilePath"
    
    $job = $jobResponse | ConvertFrom-Json
    if (-not $job.id) {
        Write-Host "  X Failed to create job" -ForegroundColor Red
        return $false
    }
    
    $jobId = $job.id
    Write-Host "  Job Created: $jobId"
    
    # 2. Poll until READY
    Write-Host "  Waiting for READY..." -NoNewline
    $maxWait = 60
    $elapsed = 0
    while ($elapsed -lt $maxWait) {
        Start-Sleep -Milliseconds 500
        $elapsed += 0.5
        $statusResp = curl.exe -s "$BaseUrl/api/v2/import/jobs/$jobId" -H "X-Tenant-Id: $TenantId"
        $job = $statusResp | ConvertFrom-Json
        
        if ($job.status -eq "READY") {
            Write-Host " READY" -ForegroundColor Green
            break
        }
        if ($job.status -eq "FAILED") { 
            Write-Host " FAILED" -ForegroundColor Red
            return $false
        }
    }
    
    if ($job.status -ne "READY") {
        Write-Host " TIMEOUT" -ForegroundColor Red
        return $false
    }
    
    # 3. Commit
    Write-Host "  Committing..." -NoNewline
    $commitResp = curl.exe -s -X POST "$BaseUrl/api/v2/import/jobs/$jobId/commit" `
        -H "X-Tenant-Id: $TenantId"
    
    # 4. Poll for COMPLETED
    $maxWait = 120
    $elapsed = 0
    while ($elapsed -lt $maxWait) {
        Start-Sleep -Seconds 1
        $elapsed += 1
        $statusResp = curl.exe -s "$BaseUrl/api/v2/import/jobs/$jobId" -H "X-Tenant-Id: $TenantId"
        $job = $statusResp | ConvertFrom-Json
        
        if ($job.status -eq "COMPLETED") {
            Write-Host " COMPLETED" -ForegroundColor Green
            return $true
        } elseif ($job.status -eq "FAILED") {
            Write-Host " FAILED" -ForegroundColor Red
            return $false
        }
    }
    
    Write-Host " TIMEOUT" -ForegroundColor Red
    return $false
}

# Import P1 Files (first 3)
Write-Host "`n=== Importing P1 Files ===" -ForegroundColor Cyan
$p1Files = Get-ChildItem -Path $P1Dir -Filter "*.csv" | Select-Object -First $Take
$p1Success = 0
$p1Total = $p1Files.Count

foreach ($file in $p1Files) {
    if (Import-File -FilePath $file.FullName -TableCode "P1" -TenantId $TenantId) {
        $p1Success++
    }
}

Write-Host "`nP1 Import Summary: $p1Success/$p1Total succeeded" -ForegroundColor $(if ($p1Success -eq $p1Total) { "Green" } else { "Yellow" })

# Import P2 Files (first 3)
Write-Host "`n=== Importing P2 Files ===" -ForegroundColor Cyan
$p2Files = Get-ChildItem -Path $P2Dir -Filter "*.csv" | Where-Object { $_.Name -notlike "merged*" } | Select-Object -First $Take
$p2Success = 0
$p2Total = $p2Files.Count

foreach ($file in $p2Files) {
    if (Import-File -FilePath $file.FullName -TableCode "P2" -TenantId $TenantId) {
        $p2Success++
    }
}

Write-Host "`nP2 Import Summary: $p2Success/$p2Total succeeded" -ForegroundColor $(if ($p2Success -eq $p2Total) { "Green" } else { "Yellow" })

# Query Test
Write-Host "`n=== Testing Query Flow (V2 API) ===" -ForegroundColor Cyan

# Query P1 Records
Write-Host "`n--- Querying P1 Records ---"
$url1 = "$BaseUrl/api/v2/records/P1?page=1&" + "page_size=5"
$p1Response = curl.exe -s $url1 -H "X-Tenant-Id: $TenantId" | ConvertFrom-Json
Write-Host "Total P1 Records: $($p1Response.total)" -ForegroundColor Green

if ($p1Response.items -and $p1Response.items.Count -gt 0) {
    Write-Host "Sample P1 Record:" -ForegroundColor Yellow
    $sample = $p1Response.items[0]
    Write-Host "  - lot_no_raw: $($sample.lot_no_raw)"
    Write-Host "  - lot_no_norm: $($sample.lot_no_norm)"
    Write-Host "  - Row count in extras: $($sample.extras.rows.Count)"
} else {
    Write-Host "No P1 records found" -ForegroundColor Yellow
}

# Query P2 Records
Write-Host "`n--- Querying P2 Records ---"
$url2 = "$BaseUrl/api/v2/records/P2?page=1&" + "page_size=5"
$p2Response = curl.exe -s $url2 -H "X-Tenant-Id: $TenantId" | ConvertFrom-Json
Write-Host "Total P2 Records: $($p2Response.total)" -ForegroundColor Green

if ($p2Response.items -and $p2Response.items.Count -gt 0) {
    Write-Host "Sample P2 Record:" -ForegroundColor Yellow
    $sample = $p2Response.items[0]
    Write-Host "  - lot_no_raw: $($sample.lot_no_raw)"
    Write-Host "  - lot_no_norm: $($sample.lot_no_norm)"
    Write-Host "  - Item rows count: $($sample.additional_data.rows.Count)"
} else {
    Write-Host "No P2 records found" -ForegroundColor Yellow
}

Write-Host "`n=== All Tests Completed ===" -ForegroundColor Cyan
$summaryMsg = "Import Results: P1=$p1Success/$p1Total, P2=$p2Success/$p2Total"
Write-Host $summaryMsg -ForegroundColor Cyan
