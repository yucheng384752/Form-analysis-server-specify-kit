# Analytics API Test Script
# Test Date: 2026-01-12
# Simplified version without encoding issues

param(
    [string]$BaseUrl = "http://localhost:18002"
)

$ErrorActionPreference = "Continue"
$testResults = @()
$testStartTime = Get-Date

Write-Host "`n=== Analytics API Test Suite ===" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Yellow
Write-Host "Start Time: $testStartTime`n" -ForegroundColor Yellow

# Get Tenant (required for /api/* endpoints)
Write-Host "Getting Tenant..." -ForegroundColor Yellow
try {
    $tenants = Invoke-RestMethod -Uri "$BaseUrl/api/tenants" -Method GET
    $tenants = @($tenants)
    if (-not $tenants -or $tenants.Count -eq 0) { throw "No tenants found" }
    $tenantId = $tenants[0].id
    $headers = @{ "X-Tenant-Id" = "$tenantId" }
    Write-Host "Using Tenant ID: $tenantId`n" -ForegroundColor Gray
} catch {
    Write-Host "[FAIL] Failed to get tenant: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 0: Health Check
Write-Host "[Test 0] Health Check" -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/api/v2/analytics/health" -Method GET -Headers $headers
    Write-Host "[PASS] Health: $($response.status)" -ForegroundColor Green
    Write-Host "  Config: max=$($response.config.max_records_per_request), rate=$($response.config.rate_limit_per_minute)/min" -ForegroundColor Gray
    $testResults += @{Test="Health"; Status="PASS"}
} catch {
    Write-Host "[FAIL] Health Check: $($_.Exception.Message)" -ForegroundColor Red
    $testResults += @{Test="Health"; Status="FAIL"}
}

# Test 1: Single Server Monthly Query (Sep 2025)
Write-Host "`n[Test 1] Single Server - Monthly Query (2025-09)" -ForegroundColor Cyan
$start1 = Get-Date
try {
    $url1 = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025&month=9"
    $response1 = Invoke-RestMethod -Uri $url1 -Method GET -Headers $headers
    $duration1 = ((Get-Date) - $start1).TotalSeconds
    
    Write-Host "[PASS] Count: $($response1.count), Has Data: $($response1.has_data), Time: $([math]::Round($duration1, 2))s" -ForegroundColor Green
    Write-Host "  Compression: $($response1.metadata.compression)" -ForegroundColor Gray
    
    if ($response1.data.Count -gt 0) {
        $first = $response1.data[0]
        $nullCount = ($first.PSObject.Properties | Where-Object { $null -eq $_.Value }).Count
        Write-Host "  First Record: LOT=$($first.'LOT NO.'), Null Fields=$nullCount" -ForegroundColor Gray
    }
    
    $testResults += @{Test="Single-Monthly"; Status="PASS"; Count=$response1.count; Time=$duration1}
    $global:monthlyData = $response1
} catch {
    $duration1 = ((Get-Date) - $start1).TotalSeconds
    Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    $testResults += @{Test="Single-Monthly"; Status="FAIL"; Time=$duration1}
}

# Test 2: Concurrent 3 Servers
Write-Host "`n[Test 2] Concurrent 3 Servers - Monthly Query" -ForegroundColor Cyan
$jobs = @()
$start2 = Get-Date

for ($i = 1; $i -le 3; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($url, $headers)
        $startTime = Get-Date
        try {
            $response = Invoke-RestMethod -Uri $url -Method GET -Headers $headers
            $duration = ((Get-Date) - $startTime).TotalSeconds
            return [PSCustomObject]@{ Success = $true; Count = $response.count; Duration = $duration }
        } catch {
            return [PSCustomObject]@{ Success = $false; Error = $_.Exception.Message; Duration = $null; Count = $null }
        }
    } -ArgumentList "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025&month=9", $headers
}

$jobResults = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
$duration2 = ((Get-Date) - $start2).TotalSeconds

$successCount = ($jobResults | Where-Object { $_.Success }).Count
if ($successCount -eq 3) {
    $avgTime = ($jobResults | Measure-Object -Property Duration -Average).Average
    Write-Host "[PASS] All 3 requests succeeded, Avg: $([math]::Round($avgTime, 2))s, Total: $([math]::Round($duration2, 2))s" -ForegroundColor Green
    $jobResults | ForEach-Object -Begin { $i=1 } -Process {
        Write-Host "  Server$($i): Count=$($_.Count), Time=$([math]::Round($_.Duration, 2))s" -ForegroundColor Gray
        $i++
    }
    $testResults += @{Test="Concurrent-3"; Status="PASS"; Time=$duration2}
} else {
    Write-Host "[FAIL] Only $successCount/3 succeeded" -ForegroundColor Red
    $testResults += @{Test="Concurrent-3"; Status="FAIL"; Time=$duration2}
}

# Test 3: Empty Data
Write-Host "`n[Test 3] Empty Data (Future Date)" -ForegroundColor Cyan
try {
    $url3 = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2050&month=12"
    $response3 = Invoke-RestMethod -Uri $url3 -Method GET -Headers $headers
    
    if ($response3.count -eq 0 -and $response3.has_data -eq $false -and $response3.data.Count -eq 0) {
        Write-Host "[PASS] Empty array semantics correct: count=0, has_data=false, data=[]" -ForegroundColor Green
        $testResults += @{Test="Empty-Data"; Status="PASS"}
    } else {
        Write-Host "[FAIL] Empty data format incorrect" -ForegroundColor Red
        $testResults += @{Test="Empty-Data"; Status="FAIL"}
    }
} catch {
    Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red
    $testResults += @{Test="Empty-Data"; Status="FAIL"}
}

# Test 4: Rate Limiting
Write-Host "`n[Test 4] Rate Limiting (35 requests)" -ForegroundColor Cyan
$start4 = Get-Date
$blocked = 0
$success = 0

for ($i = 1; $i -le 35; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025&month=9" -Method GET -Headers $headers -ErrorAction Stop
        $success++
        Write-Host "." -NoNewline -ForegroundColor Green
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 429) {
            $blocked++
            Write-Host "!" -NoNewline -ForegroundColor Red
        } else {
            Write-Host "?" -NoNewline -ForegroundColor Yellow
        }
    }
}
Write-Host ""

$duration4 = ((Get-Date) - $start4).TotalSeconds
if ($blocked -gt 0) {
    Write-Host "[PASS] Rate limit triggered: Success=$success, Blocked=$blocked, Time=$([math]::Round($duration4, 2))s" -ForegroundColor Green
    $testResults += @{Test="Rate-Limit"; Status="PASS"; Blocked=$blocked}
} else {
    Write-Host "[WARNING] Rate limit not triggered (may be disabled or interval too long)" -ForegroundColor Yellow
    $testResults += @{Test="Rate-Limit"; Status="WARNING"}
}

# Test 5: Boundary - Invalid Year
Write-Host "`n[Test 5] Boundary - Invalid Year (1900)" -ForegroundColor Cyan
try {
    $url5 = "$BaseUrl/api/v2/analytics/flatten/monthly?year=1900&month=1"
    $response5 = Invoke-RestMethod -Uri $url5 -Method GET -Headers $headers
    Write-Host "[FAIL] API accepted invalid year 1900" -ForegroundColor Red
    $testResults += @{Test="Invalid-Year"; Status="FAIL"}
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 422) {
        Write-Host "[PASS] Correctly rejected with HTTP $code" -ForegroundColor Green
        $testResults += @{Test="Invalid-Year"; Status="PASS"}
    } else {
        Write-Host "[WARNING] Rejected with HTTP $code (expected 422)" -ForegroundColor Yellow
        $testResults += @{Test="Invalid-Year"; Status="WARNING"}
    }
}

# Test 6: Boundary - Invalid Month
Write-Host "`n[Test 6] Boundary - Invalid Month (13)" -ForegroundColor Cyan
try {
    $url6 = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025&month=13"
    $response6 = Invoke-RestMethod -Uri $url6 -Method GET -Headers $headers
    Write-Host "[FAIL] API accepted invalid month 13" -ForegroundColor Red
    $testResults += @{Test="Invalid-Month"; Status="FAIL"}
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 422) {
        Write-Host "[PASS] Correctly rejected with HTTP $code" -ForegroundColor Green
        $testResults += @{Test="Invalid-Month"; Status="PASS"}
    } else {
        Write-Host "[WARNING] Rejected with HTTP $code (expected 422)" -ForegroundColor Yellow
        $testResults += @{Test="Invalid-Month"; Status="WARNING"}
    }
}

# Test 7: Boundary - Missing Parameter
Write-Host "`n[Test 7] Boundary - Missing Parameter" -ForegroundColor Cyan
try {
    $url7 = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025"
    $response7 = Invoke-RestMethod -Uri $url7 -Method GET -Headers $headers
    Write-Host "[FAIL] API accepted missing month parameter" -ForegroundColor Red
    $testResults += @{Test="Missing-Param"; Status="FAIL"}
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 422) {
        Write-Host "[PASS] Correctly rejected with HTTP $code" -ForegroundColor Green
        $testResults += @{Test="Missing-Param"; Status="PASS"}
    } else {
        Write-Host "[WARNING] Rejected with HTTP $code (expected 422)" -ForegroundColor Yellow
        $testResults += @{Test="Missing-Param"; Status="WARNING"}
    }
}

# Summary
Write-Host "`n=== Test Summary ===" -ForegroundColor Cyan
$totalTests = $testResults.Count
$passed = ($testResults | Where-Object { $_.Status -eq "PASS" }).Count
$failed = ($testResults | Where-Object { $_.Status -eq "FAIL" }).Count
$warnings = ($testResults | Where-Object { $_.Status -eq "WARNING" }).Count
$totalDuration = ((Get-Date) - $testStartTime).TotalSeconds

Write-Host "Total: $totalTests, Passed: $passed, Failed: $failed, Warnings: $warnings" -ForegroundColor White
Write-Host "Duration: $([math]::Round($totalDuration, 2)) seconds" -ForegroundColor White

# Save Report
$reportDate = Get-Date -Format "yyyyMMdd"
$reportDir = ".\test-results"
$reportPath = "$reportDir\$reportDate-analytics-api-test-report.json"

if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}

$reportData = @{
    TestDate = (Get-Date).ToString("o")
    Summary = @{
        Total = $totalTests
        Passed = $passed
        Failed = $failed
        Warnings = $warnings
        Duration = $totalDuration
    }
    Results = $testResults
    Environment = @{
        BaseUrl = $BaseUrl
        PowerShellVersion = $PSVersionTable.PSVersion.ToString()
    }
}

$reportData | ConvertTo-Json -Depth 10 | Out-File -FilePath $reportPath -Encoding UTF8
Write-Host "`nReport saved: $reportPath" -ForegroundColor Cyan

if ($failed -gt 0) {
    exit 1
} else {
    exit 0
}
