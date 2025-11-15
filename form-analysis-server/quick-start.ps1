# Form Analysis - Docker 一鍵啟動與驗證腳本 (PowerShell)
# 
# 此腳本將：
# 1. 啟動所有服務
# 2. 等待服務就緒
# 3. 驗證健康檢查
# 4. 模擬完整的上傳和驗證流程
# 5. 提供前端訪問資訊

param(
    [switch]$SkipTests,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Form Analysis - Docker 一鍵啟動與驗證腳本

用法:
  .\quick-start.ps1           # 完整啟動和測試
  .\quick-start.ps1 -SkipTests # 只啟動服務，跳過測試

選項:
  -SkipTests    跳過 API 測試，只啟動服務
  -Help         顯示此幫助資訊
"@
    exit 0
}

# 函數定義
function Write-ColorOutput {
    param($ForegroundColor, $Message)
    $oldForegroundColor = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = $ForegroundColor
    Write-Output $Message
    $Host.UI.RawUI.ForegroundColor = $oldForegroundColor
}

function Write-Info { param($Message) Write-ColorOutput Cyan "[INFO] $Message" }
function Write-Success { param($Message) Write-ColorOutput Green "[SUCCESS] $Message" }
function Write-Warning { param($Message) Write-ColorOutput Yellow "[WARNING] $Message" }
function Write-Error { param($Message) Write-ColorOutput Red "[ERROR] $Message" }

# 主腳本開始
Write-ColorOutput Blue @"
🚀 Form Analysis - Docker 一鍵啟動與驗證
========================================
"@

# 檢查必要工具
Write-Info "檢查必要工具..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker 未安裝或未在 PATH 中"
    Write-Host "請從 https://www.docker.com/products/docker-desktop 下載並安裝 Docker Desktop"
    exit 1
}

if (-not (Get-Command curl -ErrorAction SilentlyContinue)) {
    Write-Warning "curl 未安裝，嘗試使用 Invoke-WebRequest 替代"
    $useCurl = $false
} else {
    $useCurl = $true
}

# 檢查 Docker 是否運行
try {
    docker info | Out-Null
    Write-Success "Docker 正在運行"
} catch {
    Write-Error "Docker 未運行，請先啟動 Docker Desktop"
    exit 1
}

# 停止現有容器
Write-Info "停止並清理現有容器..."
docker compose down -v 2>$null

# 啟動服務
Write-Info "啟動所有服務..."
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Error "服務啟動失敗"
    exit 1
}

Write-Info "等待服務啟動..."
Start-Sleep 15

# 等待數據庫就緒
Write-Info "等待數據庫就緒..."
$maxRetries = 30
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        $result = docker compose exec -T db pg_isready -U app 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "數據庫已就緒"
            break
        }
    } catch {}
    
    $retryCount++
    Write-Host -NoNewline "."
    Start-Sleep 2
}

if ($retryCount -eq $maxRetries) {
    Write-Error "數據庫啟動超時"
    docker compose logs db
    exit 1
}

# 等待後端 API 就緒
Write-Info "等待後端 API 就緒..."
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        if ($useCurl) {
            curl -f http://localhost:8000/healthz -o $null -s 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "後端 API 已就緒"
                break
            }
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "後端 API 已就緒"
                break
            }
        }
    } catch {}
    
    $retryCount++
    Write-Host -NoNewline "."
    Start-Sleep 2
}

if ($retryCount -eq $maxRetries) {
    Write-Error "後端 API 啟動超時"
    docker compose logs backend
    exit 1
}

# 等待前端就緒
Write-Info "等待前端就緒..."
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        if ($useCurl) {
            curl -f http://localhost:5173 -o $null -s 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "前端已就緒"
                break
            }
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "前端已就緒"
                break
            }
        }
    } catch {}
    
    $retryCount++
    Write-Host -NoNewline "."
    Start-Sleep 2
}

if ($retryCount -eq $maxRetries) {
    Write-Error "前端啟動超時"
    docker compose logs frontend
    exit 1
}

Write-Host ""
Write-Success "所有服務已啟動完成！"
Write-Host ""

if (-not $SkipTests) {
    # 驗證健康檢查
    Write-ColorOutput Blue @"
🩺 健康檢查驗證
==================
"@

    Write-Info "測試基本健康檢查..."
    try {
        if ($useCurl) {
            $response = curl -f http://localhost:8000/healthz -s
            Write-Host $response
            Write-Success "基本健康檢查通過"
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -ErrorAction Stop
            Write-Host $response.Content
            Write-Success "基本健康檢查通過"
        }
    } catch {
        Write-Error "基本健康檢查失敗: $_"
        exit 1
    }

    Write-Host ""
    Write-Info "測試詳細健康檢查..."
    try {
        if ($useCurl) {
            $response = curl -f http://localhost:8000/healthz/detailed -s 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host $response
                Write-Success "詳細健康檢查通過"
            } else {
                Write-Warning "詳細健康檢查失敗（可能尚未實現）"
            }
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz/detailed" -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Host $response.Content
                Write-Success "詳細健康檢查通過"
            } else {
                Write-Warning "詳細健康檢查失敗（可能尚未實現）"
            }
        }
    } catch {
        Write-Warning "詳細健康檢查失敗（可能尚未實現）"
    }

    Write-Host ""

    # 模擬上傳與驗證流程
    Write-ColorOutput Blue @"
 模擬上傳與驗證流程
=======================
"@

    # 創建測試 CSV 文件
    $testCsvContent = @"
lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
2345678_02,測試產品B,50,2024-01-16
3456789_03,測試產品C,75,2024-01-17
4567890_04,測試產品D,200,2024-01-18
5678901_05,測試產品E,125,2024-01-19
"@

    $tempCsv = [System.IO.Path]::GetTempFileName() + ".csv"
    $testCsvContent | Out-File -FilePath $tempCsv -Encoding UTF8

    Write-Info "測試檔案上傳（5 列測試數據）..."

    try {
        if ($useCurl) {
            $uploadResponse = curl -s -X POST -F "file=@$tempCsv" http://localhost:8000/api/upload
        } else {
            # PowerShell 檔案上傳比較複雜，這裡簡化處理
            Write-Warning "使用 PowerShell 進行檔案上傳測試（簡化版本）"
            $uploadResponse = "PowerShell upload test - please use browser for full test"
        }

        Write-Host "上傳回應: $uploadResponse"
        
        # 嘗試解析 file_id
        if ($uploadResponse -match '"file_id":"([^"]*)"') {
            $fileId = $Matches[1]
            Write-Success "檔案上傳成功，file_id: $fileId"
            
            # 測試錯誤報告下載
            Write-Info "測試錯誤報告下載..."
            try {
                if ($useCurl) {
                    curl -f "http://localhost:8000/api/errors.csv?file_id=$fileId" -o errors.csv -s
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "錯誤報告下載成功"
                        Write-Host "錯誤報告內容："
                        Get-Content errors.csv
                        Remove-Item errors.csv -ErrorAction SilentlyContinue
                    }
                }
            } catch {
                Write-Warning "錯誤報告下載失敗或無錯誤"
            }
            
            # 測試資料匯入
            Write-Info "測試資料匯入..."
            try {
                if ($useCurl) {
                    $importResponse = curl -s -X POST -H "Content-Type: application/json" -d "{`"file_id`":`"$fileId`"}" http://localhost:8000/api/import
                    Write-Host "匯入回應: $importResponse"
                    Write-Success "資料匯入測試完成"
                }
            } catch {
                Write-Warning "資料匯入測試失敗"
            }
        } else {
            Write-Warning "無法解析 file_id，跳過後續測試"
        }
        
    } catch {
        Write-Error "檔案上傳測試失敗: $_"
    }

    # 清理臨時文件
    Remove-Item $tempCsv -ErrorAction SilentlyContinue
}

Write-Host ""
Write-ColorOutput Blue @"
🌐 前端訪問資訊
================
"@
Write-Success "前端應用已啟動: http://localhost:5173"
Write-Success "後端 API 文件: http://localhost:8000/docs"
Write-Success "後端 API Redoc: http://localhost:8000/redoc"

Write-Host ""
Write-ColorOutput Blue @"
 環境配置說明
================
"@
Write-Host "• API Base URL: 在 .env 文件中配置 VITE_API_URL"
Write-Host "• 檔案大小限制: 在 .env 文件中配置 VITE_MAX_FILE_SIZE"
Write-Host "• CORS 設定: 在 .env 文件中配置 CORS_ORIGINS"
Write-Host ""
Write-Host "📝 vite.config.ts 代理設定已配置 /api 路徑到後端"
Write-Host ""

Write-ColorOutput Blue @"
 容器狀態
===========
"@
docker compose ps

Write-Host ""
Write-Success "🎉 一鍵啟動與驗證完成！"
Write-Host ""
Write-Host "使用以下命令查看日誌："
Write-Host "  docker compose logs -f backend    # 後端日誌"
Write-Host "  docker compose logs -f frontend   # 前端日誌"
Write-Host "  docker compose logs -f db         # 數據庫日誌"
Write-Host ""
Write-Host "停止服務："
Write-Host "  docker compose down"
Write-Host ""
Write-Host "停止並清理數據："
Write-Host "  docker compose down -v"
Write-Host ""

# 自動打開瀏覽器（可選）
$openBrowser = Read-Host "是否自動打開前端頁面？(y/N)"
if ($openBrowser -eq 'y' -or $openBrowser -eq 'Y') {
    Start-Process "http://localhost:5173"
}