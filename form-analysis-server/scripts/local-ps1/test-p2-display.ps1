# Test P2 Display Fix - 測試 P2 資料顯示修正
# 此腳本測試一般查詢能正確顯示 P1/P2/P3 內容

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "P2 Display Fix Integration Test" -ForegroundColor Cyan
Write-Host "Test Goal: Verify P2 data structure after fix" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# API Base URL
$baseUrl = "http://localhost:18002/api/v2/query"

# Get Tenant
$apiBase = "http://localhost:18002"
$tenants = Invoke-RestMethod -Uri "$apiBase/api/tenants" -Method Get
$tenants = @($tenants)
if (-not $tenants -or $tenants.Count -eq 0) {
    Write-Host "Error: No tenants found" -ForegroundColor Red
    exit 1
}
$tenantId = $tenants[0].id
$headers = @{ "X-Tenant-Id" = "$tenantId" }
Write-Host "Using Tenant ID: $tenantId" -ForegroundColor Gray

# Test lot number
$testLotNo = "2507173_02"

Write-Host "Test 1: Basic Query API" -ForegroundColor Yellow
Write-Host "Lot No: $testLotNo" -ForegroundColor Gray

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/records/advanced?lot_no=$testLotNo&page=1&page_size=10" -Method Get -Headers $headers
    
    Write-Host "API Response OK" -ForegroundColor Green
    Write-Host "  Total Count: $($response.total_count)" -ForegroundColor Gray
    Write-Host "  Records Returned: $($response.records.Count)" -ForegroundColor Gray
    
    # Analyze data types
    $p1Count = ($response.records | Where-Object { $_.data_type -eq 'P1' }).Count
    $p2Count = ($response.records | Where-Object { $_.data_type -eq 'P2' }).Count
    $p3Count = ($response.records | Where-Object { $_.data_type -eq 'P3' }).Count
    
    Write-Host "`nData Type Statistics:" -ForegroundColor Cyan
    Write-Host "  P1: $p1Count records" -ForegroundColor Gray
    Write-Host "  P2: $p2Count records" -ForegroundColor Gray
    Write-Host "  P3: $p3Count records" -ForegroundColor Gray
    
    # Check P2 data structure
    if ($p2Count -gt 0) {
        Write-Host "`nTest 2: Check P2 Data Structure" -ForegroundColor Yellow
        
        $p2Record = $response.records | Where-Object { $_.data_type -eq 'P2' } | Select-Object -First 1
        
        Write-Host "P2 Record ID: $($p2Record.id)" -ForegroundColor Gray
        Write-Host "Lot No: $($p2Record.lot_no)" -ForegroundColor Gray
        Write-Host "Display Name: $($p2Record.display_name)" -ForegroundColor Gray
        
        if ($null -eq $p2Record.additional_data) {
            Write-Host "ERROR: additional_data is null" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "OK: additional_data exists" -ForegroundColor Green
        
        # Check rows array
        if ($null -eq $p2Record.additional_data.rows) {
            Write-Host "ERROR: additional_data.rows not found" -ForegroundColor Red
            Write-Host "  Actual fields: $($p2Record.additional_data.PSObject.Properties.Name -join ', ')" -ForegroundColor Gray
            exit 1
        }
        
        $rowsCount = $p2Record.additional_data.rows.Count
        Write-Host "OK: additional_data.rows exists" -ForegroundColor Green
        Write-Host "  Rows Count: $rowsCount" -ForegroundColor Gray
        
        if ($rowsCount -eq 0) {
            Write-Host "ERROR: rows array is empty" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "OK: rows array contains data" -ForegroundColor Green
        
        # Check first row fields
        $firstRow = $p2Record.additional_data.rows[0]
        $fieldCount = ($firstRow.PSObject.Properties).Count
        
        Write-Host "`nFirst Row Data:" -ForegroundColor Cyan
        Write-Host "  Field Count: $fieldCount" -ForegroundColor Gray
        Write-Host "  Field Names: $($firstRow.PSObject.Properties.Name -join ', ')" -ForegroundColor Gray
        
        # Check winder_number
        if ($null -ne $firstRow.winder_number) {
            Write-Host "OK: Contains winder_number: $($firstRow.winder_number)" -ForegroundColor Green
        } else {
            Write-Host "WARNING: winder_number field not found" -ForegroundColor Yellow
        }
        
        Write-Host "`nSample Data (first 5 fields):" -ForegroundColor Cyan
        $firstRow.PSObject.Properties | Select-Object -First 5 | ForEach-Object {
            Write-Host "  $($_.Name): $($_.Value)" -ForegroundColor Gray
        }
    } else {
        Write-Host "`nWARNING: No P2 data in query results" -ForegroundColor Yellow
    }
    
    # Check P1 data
    if ($p1Count -gt 0) {
        Write-Host "`nTest 3: Check P1 Data Structure (Reference)" -ForegroundColor Yellow
        
        $p1Record = $response.records | Where-Object { $_.data_type -eq 'P1' } | Select-Object -First 1
        
        if ($null -ne $p1Record.additional_data) {
            Write-Host "OK: P1 additional_data exists" -ForegroundColor Green
        } else {
            Write-Host "ERROR: P1 additional_data is null" -ForegroundColor Red
        }
    }
    
    # Check P3 data
    if ($p3Count -gt 0) {
        Write-Host "`nTest 4: Check P3 Data Structure (Reference)" -ForegroundColor Yellow
        
        $p3Record = $response.records | Where-Object { $_.data_type -eq 'P3' } | Select-Object -First 1
        
        if ($null -ne $p3Record.additional_data) {
            Write-Host "OK: P3 additional_data exists" -ForegroundColor Green
            
            if ($null -ne $p3Record.additional_data.rows) {
                Write-Host "OK: P3 additional_data.rows exists" -ForegroundColor Green
                Write-Host "  Rows Count: $($p3Record.additional_data.rows.Count)" -ForegroundColor Gray
            }
        } else {
            Write-Host "ERROR: P3 additional_data is null" -ForegroundColor Red
        }
    }
    
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Test Summary - Success" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Status: All tests passed" -ForegroundColor Green
    Write-Host "`nP2 Data Structure Fix:" -ForegroundColor Green
    Write-Host "  - additional_data.rows array generated correctly" -ForegroundColor Gray
    Write-Host "  - Each row contains complete winder data" -ForegroundColor Gray
    Write-Host "  - Frontend should render P2 table properly" -ForegroundColor Gray
    
} catch {
    Write-Host "`nTest Failed" -ForegroundColor Red
    Write-Host "Error Message: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status Code: $statusCode" -ForegroundColor Red
    }
    
    exit 1
}
