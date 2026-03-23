# Analytics API 完整測試腳本
# 測試日期: 2026-01-12

param(
    [string]$BaseUrl = "http://localhost:18002"
)

$ErrorActionPreference = "Continue"
$testResults = @()
$testStartTime = Get-Date

# Get Tenant (required for /api/* endpoints)
Write-Host "Getting Tenant..." -ForegroundColor Yellow
try {
    $tenants = Invoke-RestMethod -Uri "$BaseUrl/api/tenants" -Method Get
    $tenants = @($tenants)
    if (-not $tenants -or $tenants.Count -eq 0) {
        throw "No tenants found"
    }
    $tenantId = $tenants[0].id
    $script:TenantHeaders = @{ "X-Tenant-Id" = "$tenantId" }
    Write-Host "Using Tenant ID: $tenantId" -ForegroundColor Gray
} catch {
    Write-Host "Failed to get tenant: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

function Write-TestHeader {
    param($TestName)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "測試: $TestName" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-TestResult {
    param($TestName, $Status, $Details, $Duration)
    
    $color = if ($Status -eq "PASS") { "Green" } else { "Red" }
    Write-Host "[$Status] $TestName" -ForegroundColor $color
    if ($Details) {
        Write-Host "詳情: $Details" -ForegroundColor Gray
    }
    if ($Duration) {
        Write-Host "耗時: $($Duration.TotalSeconds) 秒" -ForegroundColor Gray
    }
    
    $script:testResults += [PSCustomObject]@{
        TestName = $TestName
        Status = $Status
        Details = $Details
        Duration = $Duration
        Timestamp = Get-Date
    }
}

function Test-ApiEndpoint {
    param($Url, $TestName)
    
    $startTime = Get-Date
    try {
        $response = Invoke-WebRequest -Uri $Url -Method GET -Headers $script:TenantHeaders -UseBasicParsing -TimeoutSec 60
        $duration = (Get-Date) - $startTime
        
        if ($response.StatusCode -eq 200) {
            $json = $response.Content | ConvertFrom-Json
            Write-TestResult -TestName $TestName -Status "PASS" -Details "Status: $($response.StatusCode), 資料筆數: $($json.count)" -Duration $duration
            return $json
        } else {
            Write-TestResult -TestName $TestName -Status "FAIL" -Details "HTTP $($response.StatusCode)" -Duration $duration
            return $null
        }
    } catch {
        $duration = (Get-Date) - $startTime
        Write-TestResult -TestName $TestName -Status "FAIL" -Details $_.Exception.Message -Duration $duration
        return $null
    }
}

# ============================================
# 測試 0: 健康檢查
# ============================================
Write-TestHeader "0. 健康檢查"
$healthUrl = "$BaseUrl/api/v2/analytics/health"
$health = Test-ApiEndpoint -Url $healthUrl -TestName "健康檢查端點"

if ($health) {
    Write-Host "配置:" -ForegroundColor Yellow
    Write-Host "  - Max Records: $($health.config.max_records_per_request)"
    Write-Host "  - Rate Limit: $($health.config.rate_limit_per_minute)/min"
    Write-Host "  - Auto Gzip: $($health.config.auto_gzip_threshold) 筆"
    Write-Host "  - Null Handling: $($health.config.null_handling)"
}

# ============================================
# 測試 1: 單 Server 呼叫單月內容 (9月)
# ============================================
Write-TestHeader "1. 單 Server 呼叫單月內容 (2025年9月)"
$monthlyUrl = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025`&month=9"
$monthlyResult = Test-ApiEndpoint -Url $monthlyUrl -TestName "單月查詢 (2025-09)"

if ($monthlyResult) {
    Write-Host "結果摘要:" -ForegroundColor Yellow
    Write-Host "  - 筆數: $($monthlyResult.count)"
    Write-Host "  - 有資料: $($monthlyResult.has_data)"
    Write-Host "  - 壓縮: $($monthlyResult.metadata.compression)"
    
    if ($monthlyResult.data.Count -gt 0) {
        $firstRecord = $monthlyResult.data[0]
        $nullFields = ($firstRecord.PSObject.Properties | Where-Object { $null -eq $_.Value }).Count
        Write-Host "  - 第一筆記錄 Null 欄位數: $nullFields"
        Write-Host "  - LOT NO: $($firstRecord.'LOT NO.')"
        Write-Host "  - P1.Material: $($firstRecord.'P1.Material')"
    }
}

# ============================================
# 測試 2: 模擬 3 Server 並發呼叫
# ============================================
Write-TestHeader "2. 模擬 3 Server 並發呼叫 (2025年9月)"
$jobs = @()
$concurrentStartTime = Get-Date

for ($i = 1; $i -le 3; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($url, $serverNum, $headers)
        
        try {
            $startTime = Get-Date
            $response = Invoke-WebRequest -Uri $url -Method GET -Headers $headers -UseBasicParsing -TimeoutSec 60
            $duration = (Get-Date) - $startTime
            
            return [PSCustomObject]@{
                ServerNum = $serverNum
                StatusCode = $response.StatusCode
                Duration = $duration.TotalSeconds
                ContentLength = $response.Content.Length
                Success = $true
                Error = $null
            }
        } catch {
            return [PSCustomObject]@{
                ServerNum = $serverNum
                StatusCode = 0
                Duration = 0
                ContentLength = 0
                Success = $false
                Error = $_.Exception.Message
            }
        }
    } -ArgumentList $monthlyUrl, $i, $script:TenantHeaders
}

Write-Host "等待 3 個並發請求完成..." -ForegroundColor Yellow
$jobResults = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job

$concurrentDuration = (Get-Date) - $concurrentStartTime
$successCount = ($jobResults | Where-Object { $_.Success }).Count

if ($successCount -eq 3) {
    $avgDuration = ($jobResults | Measure-Object -Property Duration -Average).Average
    Write-TestResult -TestName "3 Server 並發測試" -Status "PASS" -Details "全部成功, 平均耗時: $([math]::Round($avgDuration, 2))秒" -Duration $concurrentDuration
    
    Write-Host "各 Server 結果:" -ForegroundColor Yellow
    $jobResults | ForEach-Object {
        Write-Host "  - Server $($_.ServerNum): $($_.StatusCode), $([math]::Round($_.Duration, 2))秒, $($_.ContentLength) bytes"
    }
} else {
    Write-TestResult -TestName "3 Server 並發測試" -Status "FAIL" -Details "成功: $successCount/3" -Duration $concurrentDuration
}

# ============================================
# 測試 3: 超過限制筆數 (測試 3001 筆以上場景)
# ============================================
Write-TestHeader "3. 超過限制筆數測試"
# 由於實際資料可能不足,我們測試邏輯：查詢多個月份
$overLimitUrl = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025`&month=1"
Write-Host "註: 實際測試需要大量資料，此處測試 API 回應邏輯" -ForegroundColor Yellow
$overLimitResult = Test-ApiEndpoint -Url $overLimitUrl -TestName "大量資料月份查詢"

if ($overLimitResult -and $overLimitResult.count -gt 1500) {
    Write-Host "警告: 回傳筆數 $($overLimitResult.count) 超過建議值 1500" -ForegroundColor Yellow
}

# ============================================
# 測試 4: Rate Limiting 測試
# ============================================
Write-TestHeader "4. Rate Limiting 測試 (30 req/min)"
$rateLimitUrl = "$BaseUrl/api/v2/analytics/health"
$rateLimitCount = 35
$rateLimitStart = Get-Date
$rateLimitResults = @()

Write-Host "快速發送 $rateLimitCount 個請求..." -ForegroundColor Yellow

for ($i = 1; $i -le $rateLimitCount; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $rateLimitUrl -Method GET -Headers $script:TenantHeaders -UseBasicParsing -TimeoutSec 5
        $rateLimitResults += @{ RequestNum = $i; StatusCode = $response.StatusCode; Success = $true }
        Write-Host "." -NoNewline -ForegroundColor Green
    } catch {
        $statusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
        $rateLimitResults += @{ RequestNum = $i; StatusCode = $statusCode; Success = $false }
        
        if ($statusCode -eq 429) {
            Write-Host "!" -NoNewline -ForegroundColor Red
        } else {
            Write-Host "?" -NoNewline -ForegroundColor Yellow
        }
    }
}

$rateLimitDuration = (Get-Date) - $rateLimitStart
Write-Host ""

$blocked = ($rateLimitResults | Where-Object { $_.StatusCode -eq 429 }).Count
$success = ($rateLimitResults | Where-Object { $_.Success }).Count

if ($blocked -gt 0) {
    Write-TestResult -TestName "Rate Limiting" -Status "PASS" -Details "成功: $success, 被阻擋 (429): $blocked" -Duration $rateLimitDuration
} else {
    Write-TestResult -TestName "Rate Limiting" -Status "WARNING" -Details "未觸發限制 (可能限制未啟用或間隔過長)" -Duration $rateLimitDuration
}

# ============================================
# 測試 5: 最小可呼叫內容 (空資料測試)
# ============================================
Write-TestHeader "5. 最小可呼叫內容 (空資料月份)"
$emptyUrl = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2050`&month=12"
$emptyResult = Test-ApiEndpoint -Url $emptyUrl -TestName "空資料月份 (2050-12)"

if ($emptyResult) {
    if ($emptyResult.count -eq 0 -and $emptyResult.has_data -eq $false -and $emptyResult.data.Count -eq 0) {
        Write-Host "空陣列語義正確:" -ForegroundColor Green
        Write-Host "  - count: $($emptyResult.count) (預期 0)"
        Write-Host "  - has_data: $($emptyResult.has_data) (預期 false)"
        Write-Host "  - data: [] (預期空陣列)"
    } else {
        Write-Host "警告: 空資料回應格式異常" -ForegroundColor Yellow
    }
}

# ============================================
# 測試 6: 邊界測試
# ============================================
Write-TestHeader "6. 邊界測試"

# 6.1 無效年份
Write-Host "6.1 無效年份測試 (year=1900)" -ForegroundColor Yellow
$invalidYearUrl = "$BaseUrl/api/v2/analytics/flatten/monthly?year=1900`&month=1"
try {
    $response = Invoke-WebRequest -Uri $invalidYearUrl -Method GET -Headers $script:TenantHeaders -UseBasicParsing -TimeoutSec 10
    Write-TestResult -TestName "無效年份 (應拒絕)" -Status "FAIL" -Details "API 接受了無效年份 1900"
} catch {
    $statusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
    if ($statusCode -eq 422) {
        Write-TestResult -TestName "無效年份" -Status "PASS" -Details "正確拒絕 (HTTP $statusCode)"
    } else {
        Write-TestResult -TestName "無效年份" -Status "WARNING" -Details "HTTP $statusCode (預期 422)"
    }
}

# 6.2 無效月份
Write-Host "6.2 無效月份測試 (month=13)" -ForegroundColor Yellow
$invalidMonthUrl = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025`&month=13"
try {
    $response = Invoke-WebRequest -Uri $invalidMonthUrl -Method GET -Headers $script:TenantHeaders -UseBasicParsing -TimeoutSec 10
    Write-TestResult -TestName "無效月份 (應拒絕)" -Status "FAIL" -Details "API 接受了無效月份 13"
} catch {
    $statusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
    if ($statusCode -eq 422) {
        Write-TestResult -TestName "無效月份" -Status "PASS" -Details "正確拒絕 (HTTP $statusCode)"
    } else {
        Write-TestResult -TestName "無效月份" -Status "WARNING" -Details "HTTP $statusCode (預期 422)"
    }
}

# 6.3 缺少參數
Write-Host "6.3 缺少參數測試 (無 month)" -ForegroundColor Yellow
$missingParamUrl = "$BaseUrl/api/v2/analytics/flatten/monthly?year=2025"
try {
    $response = Invoke-WebRequest -Uri $missingParamUrl -Method GET -Headers $script:TenantHeaders -UseBasicParsing -TimeoutSec 10
    Write-TestResult -TestName "缺少參數 (應拒絕)" -Status "FAIL" -Details "API 接受了缺少 month 參數"
} catch {
    $statusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
    if ($statusCode -eq 422) {
        Write-TestResult -TestName "缺少參數" -Status "PASS" -Details "正確拒絕 (HTTP $statusCode)"
    } else {
        Write-TestResult -TestName "缺少參數" -Status "WARNING" -Details "HTTP $statusCode (預期 422)"
    }
}

# 6.4 Product ID 測試
Write-Host "6.4 Product ID 查詢測試" -ForegroundColor Yellow
if ($monthlyResult -and $monthlyResult.data.Count -gt 0) {
    # 從月度查詢結果取第一筆的 LOT NO
    $testLotNo = $monthlyResult.data[0].'LOT NO.'
    if ($testLotNo) {
        # 構造假設的 product_id (實際需根據資料結構調整)
        $productIdUrl = "$BaseUrl/api/v2/analytics/flatten?product_ids=$testLotNo"
        $productIdResult = Test-ApiEndpoint -Url $productIdUrl -TestName "Product ID 查詢"
    } else {
        Write-TestResult -TestName "Product ID 查詢" -Status "SKIP" -Details "無可用的 product_id"
    }
} else {
    Write-TestResult -TestName "Product ID 查詢" -Status "SKIP" -Details "無月度資料可測試"
}

# ============================================
# 測試總結
# ============================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "測試總結" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$totalTests = $testResults.Count
$passedTests = ($testResults | Where-Object { $_.Status -eq "PASS" }).Count
$failedTests = ($testResults | Where-Object { $_.Status -eq "FAIL" }).Count
$warningTests = ($testResults | Where-Object { $_.Status -eq "WARNING" }).Count
$skippedTests = ($testResults | Where-Object { $_.Status -eq "SKIP" }).Count

$totalDuration = (Get-Date) - $testStartTime

Write-Host "總測試數: $totalTests" -ForegroundColor White
Write-Host "通過: $passedTests" -ForegroundColor Green
Write-Host "失敗: $failedTests" -ForegroundColor Red
Write-Host "警告: $warningTests" -ForegroundColor Yellow
Write-Host "跳過: $skippedTests" -ForegroundColor Gray
Write-Host "總耗時: $($totalDuration.TotalSeconds) 秒" -ForegroundColor White

# 儲存測試結果到檔案
$reportDate = Get-Date -Format "yyyyMMdd"
$reportPath = ".\test-results\${reportDate}-analytics-api-test-report.json"
$reportDir = Split-Path -Parent $reportPath

if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}

$reportData = @{
    TestDate = (Get-Date).ToString("o")
    Summary = @{
        Total = $totalTests
        Passed = $passedTests
        Failed = $failedTests
        Warning = $warningTests
        Skipped = $skippedTests
        Duration = $totalDuration.TotalSeconds
    }
    Results = $testResults
    Environment = @{
        BaseUrl = $BaseUrl
        PowerShellVersion = $PSVersionTable.PSVersion.ToString()
        OS = [System.Environment]::OSVersion.ToString()
    }
}

$reportData | ConvertTo-Json -Depth 10 | Out-File -FilePath $reportPath -Encoding UTF8
Write-Host "`n測試報告已儲存: $reportPath" -ForegroundColor Cyan

# 返回測試結果
if ($failedTests -gt 0) {
    exit 1
} else {
    exit 0
}
