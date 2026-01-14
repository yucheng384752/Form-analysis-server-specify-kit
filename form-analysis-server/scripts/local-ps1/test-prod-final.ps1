param(
    [string]$BaseUrl = "http://localhost:18002",
    [string]$TenantId,
    [string]$DataDir = "C:\Users\yucheng\Desktop\侑特資料\新侑特資料",
    [int]$Take = 3
)

# Import Production Data Test Script
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
$DataDir = $DataDir
$P1Dir = Join-Path $DataDir 'P1'
$P2Dir = Join-Path $DataDir 'P2'

if (-not (Test-Path -LiteralPath $P1Dir)) { throw "P1Dir not found: $P1Dir" }
if (-not (Test-Path -LiteralPath $P2Dir)) { throw "P2Dir not found: $P2Dir" }

function Import-File {
    param(
        [string]$FilePath,
        [string]$TableCode,
        [string]$TenantId
    )
    
    $fileName = Split-Path $FilePath -Leaf
    Write-Host "`n--- Processing: $fileName" -ForegroundColor Cyan
    
    $jobResponse = curl.exe -s -X POST "$BaseUrl/api/v2/import/jobs" -H "X-Tenant-Id: $TenantId" -F "table_code=$TableCode" -F "allow_duplicate=true" -F "files=@$FilePath"
    
    $job = $jobResponse | ConvertFrom-Json
    if (-not $job.id) {
        Write-Host "  X Failed to create job" -ForegroundColor Red
        return $false
    }
    
    $jobId = $job.id
    Write-Host "  Job Created: $jobId"
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
    
    Write-Host "  Committing..." -NoNewline
    $null = curl.exe -s -X POST "$BaseUrl/api/v2/import/jobs/$jobId/commit" -H "X-Tenant-Id: $TenantId"
    
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

# Import P1 Files
Write-Host "`n=== Importing P1 Files ===" -ForegroundColor Cyan
$p1Files = Get-ChildItem -Path $P1Dir -Filter "*.csv" | Select-Object -First $Take
$p1Success = 0
$p1Total = $p1Files.Count

foreach ($file in $p1Files) {
    if (Import-File -FilePath $file.FullName -TableCode "P1" -TenantId $TenantId) {
        $p1Success++
    }
}

Write-Host "`nP1 Import Summary: $p1Success / $p1Total succeeded" -ForegroundColor $(if ($p1Success -eq $p1Total) { "Green" } else { "Yellow" })

# Import P2 Files
Write-Host "`n=== Importing P2 Files ===" -ForegroundColor Cyan
$p2Files = Get-ChildItem -Path $P2Dir -Filter "*.csv" | Where-Object { $_.Name -notlike "merged*" } | Select-Object -First $Take
$p2Success = 0
$p2Total = $p2Files.Count

foreach ($file in $p2Files) {
    if (Import-File -FilePath $file.FullName -TableCode "P2" -TenantId $TenantId) {
        $p2Success++
    }
}

Write-Host "`nP2 Import Summary: $p2Success / $p2Total succeeded" -ForegroundColor $(if ($p2Success -eq $p2Total) { "Green" } else { "Yellow" })

# Query Test
Write-Host "`n=== Testing Query Flow (V2 API) ===" -ForegroundColor Cyan

# Use a known lot_no from the imported production files (first batch)
$testLotNo = "2507173_01"

Write-Host "`n--- Querying P1 Records (data_type=P1, lot_no=$testLotNo) ---"
$p1Url = "$BaseUrl/api/v2/query/records?data_type=P1&lot_no=$testLotNo&page=1&page_size=5"
$p1Response = curl.exe -s $p1Url -H "X-Tenant-Id: $TenantId" | ConvertFrom-Json
Write-Host "Total P1 Records (matched): $($p1Response.total_count)" -ForegroundColor Green

if ($p1Response.records -and $p1Response.records.Count -gt 0) {
    Write-Host "Sample P1 Record:" -ForegroundColor Yellow
    $sample = $p1Response.records[0]
    Write-Host "  - lot_no: $($sample.lot_no)"
    if ($sample.additional_data -and $sample.additional_data.rows) {
        Write-Host "  - Row count: $($sample.additional_data.rows.Count)"
    }
}

Write-Host "`n--- Querying P2 Records (data_type=P2, lot_no=$testLotNo) ---"
$p2Url = "$BaseUrl/api/v2/query/records?data_type=P2&lot_no=$testLotNo&page=1&page_size=5"
$p2Response = curl.exe -s $p2Url -H "X-Tenant-Id: $TenantId" | ConvertFrom-Json
Write-Host "Total P2 Records (matched): $($p2Response.total_count)" -ForegroundColor Green

if ($p2Response.records -and $p2Response.records.Count -gt 0) {
    Write-Host "Sample P2 Record:" -ForegroundColor Yellow
    $sample = $p2Response.records[0]
    Write-Host "  - lot_no: $($sample.lot_no)"
    if ($sample.additional_data -and $sample.additional_data.rows) {
        Write-Host "  - Item rows count: $($sample.additional_data.rows.Count)"
    }
}

Write-Host "`n=== All Tests Completed ===" -ForegroundColor Cyan
Write-Host "Import Results: P1=$p1Success/$p1Total  P2=$p2Success/$p2Total" -ForegroundColor Cyan


