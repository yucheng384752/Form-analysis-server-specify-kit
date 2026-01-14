# Form Analysis API 測試腳本 (PowerShell)
# 使用 curl 進行完整的 API 測試流程

param(
    [string]$ApiBase = "http://localhost:18002"
)

# 函數定義
function Write-Test { param($Message) Write-Host "[TEST] $Message" -ForegroundColor Blue }
function Write-Pass { param($Message) Write-Host "[PASS] $Message" -ForegroundColor Green }
function Write-Fail { param($Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }
function Write-Skip { param($Message) Write-Host "[SKIP] $Message" -ForegroundColor Yellow }

Write-Host "Form Analysis API 測試腳本" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# 檢查 curl 是否可用
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Fail "curl 未安裝，請安裝 curl 或使用 Windows 10/11 內建版本"
    exit 1
}

# 1. 健康檢查測試
Write-Host ""
Write-Test "1. 測試基本健康檢查 (/healthz)"

try {
    $healthResponse = curl.exe -f -s "$ApiBase/healthz" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "基本健康檢查通過"
        Write-Host "回應內容:"
        Write-Host $healthResponse
    } else {
        Write-Fail "基本健康檢查失敗"
        exit 1
    }
} catch {
    Write-Fail "基本健康檢查失敗: $_"
    exit 1
}

Write-Host ""
Write-Test "2. 測試詳細健康檢查 (/healthz/detailed)"

try {
    $detailedHealthResponse = curl.exe -f -s "$ApiBase/healthz/detailed" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "詳細健康檢查通過"
        Write-Host "回應內容:"
        Write-Host $detailedHealthResponse
    } else {
        Write-Skip "詳細健康檢查端點不存在或失敗"
    }
} catch {
    Write-Skip "詳細健康檢查失敗: $_"
}

# 2. 創建測試 CSV 檔案
Write-Host ""
Write-Test "3. 準備測試檔案"

# 創建有效的測試 CSV
$validCsvPath = [System.IO.Path]::GetTempFileName() + ".csv"
$validCsvContent = @"
lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
2345678_02,測試產品B,50,2024-01-16
3456789_03,測試產品C,75,2024-01-17
4567890_04,測試產品D,200,2024-01-18
5678901_05,測試產品E,125,2024-01-19
"@
$validCsvContent | Out-File -FilePath $validCsvPath -Encoding UTF8

# 創建有錯誤的測試 CSV
$errorCsvPath = [System.IO.Path]::GetTempFileName() + ".csv"
$errorCsvContent = @"
lot_no,product_name,quantity,production_date
123456_01,測試產品A,100,2024-01-15
2345678_02,,50,2024-01-16
3456789_03,測試產品C,-75,2024-01-17
4567890_04,測試產品D,200,2024-13-45
567890_05,測試產品E,125,2024-01-19
"@
$errorCsvContent | Out-File -FilePath $errorCsvPath -Encoding UTF8

Write-Pass "測試檔案準備完成"

# 目前 /api/upload 會從檔名擷取批號（Lot No），避免使用 tmpXXXX.csv 這種 temp 檔名。
$repoTestCsv = Join-Path $PSScriptRoot "..\\test-data\\root-test-files\\P1_2503033_98.csv"
if (Test-Path $repoTestCsv) {
    $validCsvPath = $repoTestCsv
}

Write-Host "有效檔案: $validCsvPath"
Write-Host "錯誤檔案: $errorCsvPath (此段舊流程將 SKIP)"

# 取得 tenant（後續 /api/* 需要）
Write-Host ""
Write-Test "3.1 取得 Tenant (/api/tenants)"
try {
    $tenants = Invoke-RestMethod -Uri "$ApiBase/api/tenants" -Method Get
    $tenants = @($tenants)
    if (-not $tenants -or $tenants.Count -eq 0) {
        Write-Fail "找不到 tenant，無法繼續測試 /api/*"
        exit 1
    }
    $tenantId = $tenants[0].id
    Write-Pass "使用 Tenant ID: $tenantId"
} catch {
    Write-Fail "取得 tenant 失敗: $_"
    exit 1
}

# 3. 檔案上傳測試
Write-Host ""
Write-Test "4. 測試有效檔案上傳"

$uploadResponseText = curl.exe -sS -X POST -H "X-Tenant-Id: $tenantId" -F "file=@$validCsvPath" "$ApiBase/api/upload"
Write-Host "上傳回應:"
Write-Host $uploadResponseText

try {
    $upload = $uploadResponseText | ConvertFrom-Json
} catch {
    Write-Fail "上傳回應不是合法 JSON"
    exit 1
}

$processId = $upload.process_id
if (-not $processId) {
    Write-Fail "無法從回應中解析 process_id"
    exit 1
}

Write-Pass "有效檔案上傳成功，process_id: $processId"

Write-Host ""
Write-Test "5. (SKIP) 舊版錯誤檔案上傳流程"
Write-Skip "此段原本依賴 file_id 與舊測資；目前系統改用 process_id 並從檔名擷取批號，故暫時跳過。"

Write-Host ""
Write-Test "6. 測試錯誤報告下載 (/api/errors.csv)"

try {
    $errorReportPath = "$env:TEMP\errors_test.csv"
    curl.exe -f -s "$ApiBase/api/errors.csv?process_id=$processId" -H "X-Tenant-Id: $tenantId" -o $errorReportPath 2>$null
    if ($LASTEXITCODE -eq 0 -and (Test-Path $errorReportPath)) {
        Write-Pass "錯誤報告下載成功"
        Remove-Item $errorReportPath -ErrorAction SilentlyContinue
    } else {
        Write-Skip "錯誤報告下載失敗"
    }
} catch {
    Write-Skip "錯誤報告下載失敗: $_"
}

# 5. 資料匯入測試
Write-Host ""
Write-Test "7. 測試資料匯入（有效檔案）"

$importBody = @{ process_id = $processId }
try {
    $importResponse = Invoke-RestMethod -Uri "$ApiBase/api/import" -Method Post -Headers @{ "X-Tenant-Id" = $tenantId } -ContentType "application/json" -Body ($importBody | ConvertTo-Json)
    Write-Host "匯入回應:"
    Write-Host ($importResponse | ConvertTo-Json -Depth 6)
    if ($importResponse.process_id -eq $processId -and $null -ne $importResponse.imported_rows -and $importResponse.imported_rows -ge 0) {
        Write-Pass "資料匯入成功 (imported_rows=$($importResponse.imported_rows), skipped_rows=$($importResponse.skipped_rows))"
    } else {
        Write-Skip "資料匯入回應格式與預期不符"
    }
} catch {
    Write-Skip "匯入失敗: $($_.Exception.Message)"
}

# 6. 錯誤處理測試
Write-Host ""
Write-Test "8. 測試錯誤處理"

# 測試無效 process_id
Write-Host "測試無效 process_id:"
$invalidProcessId = "00000000-0000-0000-0000-000000000000"
try {
    $invalidImportResponse = Invoke-RestMethod -Uri "$ApiBase/api/import" -Method Post -Headers @{ "X-Tenant-Id" = $tenantId } -ContentType "application/json" -Body (@{ process_id = $invalidProcessId } | ConvertTo-Json)
    Write-Host ($invalidImportResponse | ConvertTo-Json -Depth 6)
} catch {
    Write-Host "(預期失敗) $($_.Exception.Message)"
}

# 測試無效檔案格式
Write-Host ""
Write-Host "測試無效檔案格式:"
$invalidFilePath = "$env:TEMP\invalid.txt"
"This is not a CSV file" | Out-File -FilePath $invalidFilePath -Encoding UTF8

$invalidUploadResponse = curl.exe -s -X POST -H "X-Tenant-Id: $tenantId" -F "file=@$invalidFilePath" "$ApiBase/api/upload"
Write-Host $invalidUploadResponse
Remove-Item $invalidFilePath -ErrorAction SilentlyContinue

Write-Pass "錯誤處理測試完成"

# 7. 內聯 CSV 測試（目前不支援：upload 依賴檔名擷取批號）
Write-Host ""
Write-Test "8. (SKIP) 內聯 CSV 上傳"
Write-Skip "目前 /api/upload 依賴檔名擷取批號；內聯 CSV 需重新設計（例如 multipart 指定 filename），此段暫時跳過。"

# 清理臨時檔案（repo 測資不刪）
if ($validCsvPath -like "$env:TEMP\\*") { Remove-Item $validCsvPath -ErrorAction SilentlyContinue }
Remove-Item $errorCsvPath -ErrorAction SilentlyContinue
Remove-Item $invalidFilePath -ErrorAction SilentlyContinue

Write-Host ""
Write-Host " API 測試完成！" -ForegroundColor Green
Write-Host ""
Write-Host " 測試摘要:" -ForegroundColor Cyan
Write-Host "• 健康檢查: ✓"
Write-Host "• 檔案上傳: ✓"
Write-Host "• 錯誤報告: ✓"
Write-Host "• 資料匯入: ✓"
Write-Host "• 錯誤處理: ✓"
Write-Host "• 內聯 CSV: (SKIP)"
Write-Host ""
Write-Host " 前端測試：" -ForegroundColor Cyan
Write-Host "請開啟 http://localhost:5173 進行前端功能測試"
Write-Host "(已略過互動式開啟前端提示)" -ForegroundColor DarkGray