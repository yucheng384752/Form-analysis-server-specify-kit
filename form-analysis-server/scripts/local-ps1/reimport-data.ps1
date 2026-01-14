param(
    [string]$ApiBase = "http://localhost:18002",
    [string]$DataPath,
    [string]$TenantId
)

# 資料重新匯入腳本 (V2 Import API)
# 批號: 2507173_02

$baseUrl = "$ApiBase/api/v2/import"
$faRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
if (-not $DataPath) {
    $DataPath = Join-Path $faRoot "test-import-data"
}

# Get Tenant (required for /api/* endpoints)
Write-Host "Getting Tenant..." -ForegroundColor Yellow
try {
    if (-not $TenantId) {
        $tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get
        $tenants = @($tenants)
        if (-not $tenants -or $tenants.Count -eq 0) {
            throw "No tenants found"
        }
        $TenantId = $tenants[0].id
    }
    $script:Headers = @{ "X-Tenant-Id" = "$TenantId" }
    Write-Host "Using Tenant ID: $TenantId" -ForegroundColor Gray
} catch {
    Write-Host "[錯誤] 無法取得 tenant: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "=== 開始匯入資料到 V2 表 ===" -ForegroundColor Cyan
Write-Host ""

# 函數: 執行匯入
function Import-DataFile {
    param(
        [string]$TableCode,
        [string]$FilePath
    )
    
    Write-Host "匯入 $TableCode 資料..." -ForegroundColor Yellow
    Write-Host "  檔案: $FilePath"
    
    if (-not (Test-Path $FilePath)) {
        Write-Host "  [錯誤] 檔案不存在!" -ForegroundColor Red
        return $false
    }
    
    try {
        # 建立匯入任務
        $form = @{
            table_code = $TableCode
            files = Get-Item $FilePath
        }
        
        $response = Invoke-RestMethod -Uri "$baseUrl/jobs" -Method Post -Headers $script:Headers -Form $form -ContentType 'multipart/form-data'
        $jobId = $response.id
        Write-Host "  [成功] 任務已建立: $jobId" -ForegroundColor Green
        
        # 等待處理完成
        Write-Host "  等待處理中..." -NoNewline
        $maxWait = 60  # 最多等 60 秒
        $waited = 0
        
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 2
            $waited += 2
            Write-Host "." -NoNewline
            
            $job = Invoke-RestMethod -Uri "$baseUrl/jobs/$jobId" -Method Get -Headers $script:Headers
            
            $status = ($job.status | ForEach-Object { "$_" }).ToUpperInvariant()
            if ($status -eq "COMPLETED") {
                Write-Host ""
                Write-Host "  [完成] 狀態: $($job.status)" -ForegroundColor Green
                Write-Host "    總筆數: $($job.total_rows)"
                Write-Host "    有效: $($job.valid_rows)"
                Write-Host "    錯誤: $($job.error_rows)"
                return $true
            }
            elseif ($status -eq "FAILED") {
                Write-Host ""
                Write-Host "  [失敗] 狀態: $($job.status)" -ForegroundColor Red
                Write-Host "    錯誤訊息: $($job.error_message)"
                return $false
            }
        }
        
        Write-Host ""
        Write-Host "  [超時] 處理超過 $maxWait 秒" -ForegroundColor Yellow
        return $false
    }
    catch {
        Write-Host ""
        Write-Host "  [錯誤] $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# 函數: 提交批次資料
function Commit-Batch {
    param([string]$JobId)
    
    Write-Host "  提交批次資料..." -NoNewline
    try {
        $response = Invoke-RestMethod -Uri "$baseUrl/jobs/$JobId/commit" -Method Post -Headers $script:Headers
        Write-Host " [成功]" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host " [失敗] $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# 匯入 P1
Write-Host "【步驟 1】匯入 P1 資料" -ForegroundColor Cyan
$p1File = Join-Path $DataPath "P1_2507173_02.csv"
$p1Success = Import-DataFile -TableCode "P1" -FilePath $p1File
Write-Host ""

if (-not $p1Success) {
    Write-Host "[中止] P1 匯入失敗" -ForegroundColor Red
    exit 1
}

# 匯入 P2
Write-Host "【步驟 2】匯入 P2 資料" -ForegroundColor Cyan
$p2File = Join-Path $DataPath "P2_2507173_02.csv"
$p2Success = Import-DataFile -TableCode "P2" -FilePath $p2File
Write-Host ""

if (-not $p2Success) {
    Write-Host "[警告] P2 匯入失敗" -ForegroundColor Yellow
}

# 檢查資料庫記錄數
Write-Host "【驗證】檢查資料庫" -ForegroundColor Cyan
docker exec form_analysis_db psql -U app -d form_analysis_db -c @"
SELECT 
  'p1_records' as table_name, COUNT(*) as count FROM p1_records
UNION ALL
SELECT 'p2_records', COUNT(*) FROM p2_records
UNION ALL
SELECT 'p3_records', COUNT(*) FROM p3_records;
"@
Write-Host ""

# 測試 API
Write-Host "【測試】API 查詢" -ForegroundColor Cyan
try {
    $apiResponse = Invoke-RestMethod -Uri "http://localhost:18002/api/v2/query/records/advanced?lot_no=2507173_02" -Method Get -Headers $script:Headers
    Write-Host "  總筆數: $($apiResponse.total_count)" -ForegroundColor Green
    Write-Host "  P1: $($apiResponse.records | Where-Object { $_.data_type -eq 'P1' } | Measure-Object | Select-Object -ExpandProperty Count) 筆"
    Write-Host "  P2: $($apiResponse.records | Where-Object { $_.data_type -eq 'P2' } | Measure-Object | Select-Object -ExpandProperty Count) 筆"
    Write-Host "  P3: $($apiResponse.records | Where-Object { $_.data_type -eq 'P3' } | Measure-Object | Select-Object -ExpandProperty Count) 筆"
}
catch {
    Write-Host "  [錯誤] $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== 匯入完成 ===" -ForegroundColor Cyan
Write-Host "請開啟 http://localhost:18003 驗證前端顯示"
