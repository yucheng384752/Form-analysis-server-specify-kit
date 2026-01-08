# test-query-v2-trace.ps1
# 測試 L3-2 Traceability Search (Advanced Search + Trace Detail)

$baseUrl = "http://localhost:18002/api/v2/query"

# 1. 測試 Advanced Search (找最近的 P1)
Write-Host "1. Testing Advanced Search (Recent P1)..."
# Escape quotes for PowerShell string passing to executable
$searchBody = '{\"page\": 1, \"page_size\": 5}'

$response1Json = curl.exe -s -X POST "$baseUrl/advanced" -H "Content-Type: application/json" -d $searchBody
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
        $response2Json = curl.exe -s -X GET "$baseUrl/trace/$firstTraceKey"
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
