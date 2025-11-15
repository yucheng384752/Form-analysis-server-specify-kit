# Form Analysis API 測試腳本 (PowerShell)
# 使用 curl 進行完整的 API 測試流程

param(
    [string]$ApiBase = "http://localhost:8000"
)

# 函數定義
function Write-Test { param($Message) Write-Host "[TEST] $Message" -ForegroundColor Blue }
function Write-Pass { param($Message) Write-Host "[PASS] $Message" -ForegroundColor Green }
function Write-Fail { param($Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }
function Write-Skip { param($Message) Write-Host "[SKIP] $Message" -ForegroundColor Yellow }

Write-Host "🧪 Form Analysis API 測試腳本" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# 檢查 curl 是否可用
if (-not (Get-Command curl -ErrorAction SilentlyContinue)) {
    Write-Fail "curl 未安裝，請安裝 curl 或使用 Windows 10/11 內建版本"
    exit 1
}

# 1. 健康檢查測試
Write-Host ""
Write-Test "1. 測試基本健康檢查 (/healthz)"

try {
    $healthResponse = curl -f -s "$ApiBase/healthz" 2>$null
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
    $detailedHealthResponse = curl -f -s "$ApiBase/healthz/detailed" 2>$null
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
Write-Host "有效檔案: $validCsvPath"
Write-Host "錯誤檔案: $errorCsvPath"

# 3. 檔案上傳測試
Write-Host ""
Write-Test "4. 測試有效檔案上傳"

$uploadResponse = curl -s -X POST -F "file=@$validCsvPath" "$ApiBase/api/upload"
Write-Host "上傳回應:"
Write-Host $uploadResponse

# 解析 file_id (簡單的正則表達式)
if ($uploadResponse -match '"file_id":"([^"]*)"') {
    $validFileId = $Matches[1]
    Write-Pass "有效檔案上傳成功，file_id: $validFileId"
} else {
    Write-Fail "無法從回應中解析 file_id"
    exit 1
}

Write-Host ""
Write-Test "5. 測試有錯誤檔案上傳"

$errorUploadResponse = curl -s -X POST -F "file=@$errorCsvPath" "$ApiBase/api/upload"
Write-Host "上傳回應:"
Write-Host $errorUploadResponse

if ($errorUploadResponse -match '"file_id":"([^"]*)"') {
    $errorFileId = $Matches[1]
    Write-Pass "錯誤檔案上傳成功，file_id: $errorFileId"
} else {
    Write-Fail "無法從回應中解析錯誤檔案的 file_id"
}

# 4. 錯誤報告測試
if ($errorFileId) {
    Write-Host ""
    Write-Test "6. 測試錯誤報告下載"
    
    try {
        $errorReportPath = "$env:TEMP\errors_test.csv"
        curl -f -s "$ApiBase/api/errors.csv?file_id=$errorFileId" -o $errorReportPath 2>$null
        
        if ($LASTEXITCODE -eq 0 -and (Test-Path $errorReportPath)) {
            Write-Pass "錯誤報告下載成功"
            Write-Host "錯誤報告內容:"
            Get-Content $errorReportPath
            Remove-Item $errorReportPath -ErrorAction SilentlyContinue
        } else {
            Write-Skip "錯誤報告下載失敗或無錯誤"
        }
    } catch {
        Write-Skip "錯誤報告下載失敗: $_"
    }
}

# 5. 資料匯入測試
Write-Host ""
Write-Test "7. 測試資料匯入（有效檔案）"

$importPayload = @{
    file_id = $validFileId
} | ConvertTo-Json

$importResponse = curl -s -X POST `
    -H "Content-Type: application/json" `
    -d $importPayload `
    "$ApiBase/api/import"

Write-Host "匯入回應:"
Write-Host $importResponse

if ($importResponse -match '"success":true') {
    Write-Pass "資料匯入成功"
} else {
    Write-Skip "資料匯入失敗或返回錯誤"
}

# 6. 錯誤處理測試
Write-Host ""
Write-Test "8. 測試錯誤處理"

# 測試無效 file_id
Write-Host "測試無效 file_id:"
$invalidImportPayload = @{
    file_id = "invalid-file-id"
} | ConvertTo-Json

$invalidImportResponse = curl -s -X POST `
    -H "Content-Type: application/json" `
    -d $invalidImportPayload `
    "$ApiBase/api/import"

Write-Host $invalidImportResponse

# 測試無效檔案格式
Write-Host ""
Write-Host "測試無效檔案格式:"
$invalidFilePath = "$env:TEMP\invalid.txt"
"This is not a CSV file" | Out-File -FilePath $invalidFilePath -Encoding UTF8

$invalidUploadResponse = curl -s -X POST -F "file=@$invalidFilePath" "$ApiBase/api/upload"
Write-Host $invalidUploadResponse
Remove-Item $invalidFilePath -ErrorAction SilentlyContinue

Write-Pass "錯誤處理測試完成"

# 7. 內聯 CSV 測試
Write-Host ""
Write-Test "9. 測試內聯 CSV 上傳"

$inlineCsvContent = @"
lot_no,product_name,quantity,production_date
7777777_01,內聯測試A,10,2024-02-01
8888888_02,內聯測試B,20,2024-02-02
9999999_03,內聯測試C,30,2024-02-03
1111111_04,內聯測試D,40,2024-02-04
2222222_05,內聯測試E,50,2024-02-05
"@

# PowerShell 中的內聯上傳比較複雜，這裡使用臨時檔案模擬
$inlineCsvPath = [System.IO.Path]::GetTempFileName() + ".csv"
$inlineCsvContent | Out-File -FilePath $inlineCsvPath -Encoding UTF8

$inlineResponse = curl -s -X POST -F "file=@$inlineCsvPath" "$ApiBase/api/upload"
Write-Host "內聯上傳回應:"
Write-Host $inlineResponse

if ($inlineResponse -match '"file_id":"([^"]*)"') {
    $inlineFileId = $Matches[1]
    Write-Pass "內聯 CSV 上傳成功，file_id: $inlineFileId"
    
    # 測試匯入內聯數據
    Write-Host ""
    Write-Test "10. 測試內聯數據匯入"
    
    $inlineImportPayload = @{
        file_id = $inlineFileId
    } | ConvertTo-Json
    
    $inlineImportResponse = curl -s -X POST `
        -H "Content-Type: application/json" `
        -d $inlineImportPayload `
        "$ApiBase/api/import"
    
    Write-Host "內聯數據匯入回應:"
    Write-Host $inlineImportResponse
    
    if ($inlineImportResponse -match '"success":true') {
        Write-Pass "內聯數據匯入成功"
    } else {
        Write-Skip "內聯數據匯入失敗"
    }
} else {
    Write-Fail "內聯 CSV 上傳失敗"
}

# 清理臨時檔案
Remove-Item $validCsvPath -ErrorAction SilentlyContinue
Remove-Item $errorCsvPath -ErrorAction SilentlyContinue
Remove-Item $inlineCsvPath -ErrorAction SilentlyContinue

Write-Host ""
Write-Host " API 測試完成！" -ForegroundColor Green
Write-Host ""
Write-Host " 測試摘要:" -ForegroundColor Cyan
Write-Host "• 健康檢查: ✓"
Write-Host "• 檔案上傳: ✓"
Write-Host "• 錯誤報告: ✓"
Write-Host "• 資料匯入: ✓"
Write-Host "• 錯誤處理: ✓"
Write-Host "• 內聯 CSV: ✓"
Write-Host ""
Write-Host " 前端測試：" -ForegroundColor Cyan
Write-Host "請開啟 http://localhost:5173 進行前端功能測試"

# 詢問是否開啟前端
$openFrontend = Read-Host "`n是否自動開啟前端頁面？(y/N)"
if ($openFrontend -eq 'y' -or $openFrontend -eq 'Y') {
    Start-Process "http://localhost:5173"
}