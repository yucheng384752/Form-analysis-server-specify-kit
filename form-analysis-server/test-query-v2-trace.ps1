# test-query-v2-trace.ps1
# 測試 L3-2 Traceability Search (Advanced Search + Trace Detail)

$ApiBase = "http://localhost:18002"
$baseUrl = "$ApiBase/api/v2/query"

# 0. Get Tenant
Write-Host "0. Getting Tenant..."
try {
    $tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get
    $tenants = @($tenants)
    if (-not $tenants -or $tenants.Count -eq 0) {
        Write-Host "Error: No tenants found" -ForegroundColor Red
        exit 1
    }
    $tenantId = $tenants[0].id
    Write-Host "Using Tenant ID: $tenantId"
} catch {
    Write-Host "Error: Failed to get tenants" -ForegroundColor Red
    Write-Host $_
    exit 1
}

# 1. 測試 Advanced Search (找最近的 P1)
Write-Host "1. Testing Advanced Search (by Lot No)..."

# 1a. 先抓一個現成 lot_no（避免 default recent-P1 在沒有 P1 資料時回空）
$lotNo = $null
try {
    $recordsJson = curl.exe -s -X GET "$baseUrl/records?page=1&page_size=1" -H "X-Tenant-Id: $tenantId"
    $records = $recordsJson | ConvertFrom-Json
    if ($records.records -and $records.records.Count -gt 0) {
        $lotNo = $records.records[0].lot_no
    }
} catch {
    # ignore
}

if (-not $lotNo) {
    $lotNo = "2507173_02"
}

$searchBody = @{ lot_no = $lotNo; page = 1; page_size = 5 } | ConvertTo-Json -Compress
$response1Json = $searchBody | curl.exe -s -X POST "$baseUrl/advanced" -H "Content-Type: application/json" -H "X-Tenant-Id: $tenantId" --data-binary "@-"
Write-Host "Raw Response 1: $response1Json"

try {
    $response1 = $response1Json | ConvertFrom-Json
    $total = $response1.total
    Write-Host "   Total Results: $total"
    
    if ($response1.results.Count -gt 0) {
        $firstTraceKey = $response1.results[0].trace_key
        Write-Host "   First Trace Key: $firstTraceKey"
        
        # 2. 測試 Trace Detail
        Write-Host "`n2. Testing Trace Detail for Key: $firstTraceKey..."
        $response2Json = curl.exe -s -X GET "$baseUrl/trace/$firstTraceKey" -H "X-Tenant-Id: $tenantId"
        Write-Host "Raw Response 2: $response2Json"
        
        $response2 = $response2Json | ConvertFrom-Json
        
        if ($response2.trace_key -eq $firstTraceKey) {
            Write-Host "   [OK] Trace Key matches"
        } else {
            Write-Host "   [FAIL] Trace Key mismatch"
        }
        
        if ($response2.p1) {
            Write-Host "   [OK] P1 Record found"
        } else {
            Write-Host "   [INFO] P1 Record not found (might be expected)"
        }
        
        Write-Host "   P2 Records: $($response2.p2.Count)"
        Write-Host "   P3 Records: $($response2.p3.Count)"
        
    } else {
        Write-Host "   [WARN] No results found to test trace detail."
    }
} catch {
    Write-Host "Failed to parse JSON response"
    Write-Host $_
}
