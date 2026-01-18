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
    [switch]$ResetDb,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Form Analysis - Docker 一鍵啟動與驗證腳本

用法:
  .\quick-start.ps1           # 完整啟動和測試
  .\quick-start.ps1 -SkipTests # 只啟動服務，跳過測試

    # (危險) 清空資料庫：會移除 docker volumes（PostgreSQL 資料會消失）
    .\quick-start.ps1 -ResetDb

選項:
  -SkipTests    跳過 API 測試，只啟動服務
    -ResetDb      (危險) 移除 Docker volumes，等同清空資料庫
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
 Form Analysis - Docker 一鍵啟動與驗證
========================================
"@

# 檢查必要工具
Write-Info "檢查必要工具..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker 未安裝或未在 PATH 中"
    Write-Host "請從 https://www.docker.com/products/docker-desktop 下載並安裝 Docker Desktop"
    exit 1
}

# 注意：Windows PowerShell 5.1 中 `curl` 常是 Invoke-WebRequest 的別名。
# 這裡明確檢查/使用 curl.exe，避免 alias 行為差異。
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Warning "找不到 curl.exe，嘗試使用 Invoke-WebRequest 替代"
    $useCurl = $false
} else {
    $useCurl = $true
}

# 檢查 Docker 是否執行
try {
    docker info | Out-Null
    Write-Success "Docker 正在執行"
} catch {
    Write-Error "Docker 未執行，請先啟動 Docker Desktop"
    exit 1
}

# 停止現有容器
Write-Info "停止現有容器..."
if ($ResetDb) {
    Write-Warning "ResetDb=true：將移除 Docker volumes，資料庫資料會被清空"
    docker compose down -v --remove-orphans 2>$null
} else {
    # Default: keep volumes to preserve DB data
    docker compose down --remove-orphans 2>$null
}

# 啟動服務
Write-Info "啟動所有服務..."
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Error "服務啟動失敗"
    exit 1
}

Write-Info "等待服務啟動..."
Start-Sleep 15

# 等待資料庫就緒
Write-Info "等待資料庫就緒..."
$maxRetries = 30
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        $result = docker compose exec -T db pg_isready -U app 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "資料庫已就緒"
            break
        }
    } catch {}
    
    $retryCount++
    Write-Host -NoNewline "."
    Start-Sleep 2
}

if ($retryCount -eq $maxRetries) {
    Write-Error "資料庫啟動超時"
    docker compose logs db
    exit 1
}

# 等待後端 API 就緒
Write-Info "等待後端 API 就緒..."
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        if ($useCurl) {
            curl.exe -f http://localhost:18002/healthz -o $null -s 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "後端 API 已就緒"
                break
            }
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:18002/healthz" -TimeoutSec 5 -ErrorAction SilentlyContinue
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
            curl.exe -f http://localhost:18003 -o $null -s 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "前端已就緒"
                break
            }
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:18003" -TimeoutSec 5 -ErrorAction SilentlyContinue
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
            $response = curl.exe -f http://localhost:18002/healthz -s
            Write-Host $response
            Write-Success "基本健康檢查通過"
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:18002/healthz" -ErrorAction Stop
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
            $response = curl.exe -f http://localhost:18002/healthz/detailed -s 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host $response
                Write-Success "詳細健康檢查通過"
            } else {
                Write-Warning "詳細健康檢查失敗（可能尚未實現）"
            }
        } else {
            $response = Invoke-WebRequest -Uri "http://localhost:18002/healthz/detailed" -ErrorAction SilentlyContinue
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

    # 優先使用 repo 內既有測試檔（檔名符合 P1/P2 批號擷取規則）
    $testCsvPath = $null
    $repoTestCsv = Join-Path $PSScriptRoot "..\\test-data\\root-test-files\\P1_2503033_98.csv"
    if (Test-Path $repoTestCsv) {
        $testCsvPath = (Resolve-Path $repoTestCsv).Path
    } else {
        # fallback：建立一個檔名符合規則的暫存檔
        $testCsvContent = @"
lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
2345678_02,測試產品B,50,2024-01-16
3456789_03,測試產品C,75,2024-01-17
4567890_04,測試產品D,200,2024-01-18
5678901_05,測試產品E,125,2024-01-19
"@

        $testCsvPath = Join-Path ([System.IO.Path]::GetTempPath()) "P1_2503033_01.csv"
        $testCsvContent | Out-File -FilePath $testCsvPath -Encoding UTF8
    }

    Write-Info "測試檔案上傳: $testCsvPath"

    # Docker compose 預設可能已啟用 AUTH_MODE=api_key。
    # 若 /api/tenants 回 401，代表需要先 bootstrap 一把 tenant API key。
    $rawKey = $null
    $authEnabled = $false
    try {
        if ($useCurl) {
            $status = curl.exe -s -o $null -w "%{http_code}" http://localhost:18002/api/tenants
            if ($status -eq "401") {
                $authEnabled = $true
            }
        } else {
            # Invoke-RestMethod 對 401 會 throw；用這個作為判斷。
            Invoke-RestMethod -Uri "http://localhost:18002/api/tenants" -ErrorAction Stop | Out-Null
        }
    } catch {
        $authEnabled = $true
    }

    if ($authEnabled) {
        Write-Info "偵測到 API key auth 已啟用，bootstrap 測試用 API key..."
        try {
            $bootstrapOut = docker compose exec -T backend python scripts/bootstrap_tenant_api_key.py --tenant-code default --label docker-quick-start --force
            $lines = ($bootstrapOut -split "`r?`n") | Where-Object { $_.Trim().Length -gt 0 }
            $markerIndex = $lines.IndexOf("SAVE THIS KEY NOW (shown once):")
            if ($markerIndex -ge 0 -and ($markerIndex + 1) -lt $lines.Count) {
                $rawKey = $lines[$markerIndex + 1].Trim()
            }
            if (-not $rawKey) {
                # Fallback: take last non-empty line
                $rawKey = $lines[-1].Trim()
            }
            Write-Success "已建立/取得測試用 API key（請在註冊頁貼上）：$rawKey"
        } catch {
            Write-Error "bootstrap API key 失敗: $($_.Exception.Message)"
            exit 1
        }
    }

    # 取得 tenant（多租戶模式下 /api/* 需要 X-Tenant-Id）
    $tenantId = $null
    try {
        if ($useCurl) {
            if ($rawKey) {
                $tenantsJson = curl.exe -s -H "X-API-Key: $rawKey" http://localhost:18002/api/tenants
            } else {
                $tenantsJson = curl.exe -s http://localhost:18002/api/tenants
            }
            $tenants = $tenantsJson | ConvertFrom-Json
        } else {
            if ($rawKey) {
                $tenants = Invoke-RestMethod -Uri "http://localhost:18002/api/tenants" -Headers @{ "X-API-Key" = $rawKey } -ErrorAction Stop
            } else {
                $tenants = Invoke-RestMethod -Uri "http://localhost:18002/api/tenants" -ErrorAction Stop
            }
        }

        if ($tenants -and $tenants.Count -gt 0 -and $tenants[0].id) {
            $tenantId = $tenants[0].id
            Write-Info "使用 Tenant ID: $tenantId"
        }
    } catch {
        Write-Warning "無法取得 tenant 清單：$($_.Exception.Message)"
    }

    if (-not $tenantId) {
        Write-Error "無法取得 Tenant ID，無法進行上傳/匯入 smoke test"
        exit 1
    }

    try {
        if (-not $useCurl) {
            Write-Warning "使用 PowerShell 進行 v2 匯入測試需要 curl.exe；此段跳過。"
        } else {
            # v2 匯入（建議流程）：POST /api/v2/import/jobs -> poll READY -> POST /commit
            $headers = @("-H", "X-Tenant-Id: $tenantId")
            if ($rawKey) {
                $headers += @("-H", "X-API-Key: $rawKey")
            }

            $tableCode = "P1"
            try {
                $fn = [System.IO.Path]::GetFileName($testCsvPath)
                if ($fn -match '^(P[123])_') { $tableCode = $Matches[1] }
            } catch {}

            Write-Info "測試 v2 匯入（table_code=$tableCode）..."
            $jobCreateResp = curl.exe -s -X POST @headers -F "table_code=$tableCode" -F "allow_duplicate=false" -F "files=@$testCsvPath" http://localhost:18002/api/v2/import/jobs
            Write-Host "建立 job 回應: $jobCreateResp"

            if ($jobCreateResp -match '"id"\s*:\s*"([^"]+)"') {
                $jobId = $Matches[1]
                Write-Success "已建立 import job: $jobId"

                $status = ""
                for ($i = 0; $i -lt 30; $i++) {
                    Start-Sleep -Seconds 1
                    $jobStatusResp = curl.exe -s -X GET @headers "http://localhost:18002/api/v2/import/jobs/$jobId"
                    if ($jobStatusResp -match '"status"\s*:\s*"([^"]+)"') {
                        $status = $Matches[1]
                        Write-Info "job status: $status"
                        if ($status -eq "READY" -or $status -eq "FAILED") { break }
                    }
                }

                if ($status -eq "FAILED") {
                    Write-Warning "匯入 job 失敗（可用 /api/v2/import/jobs/$jobId/errors 檢視錯誤）"
                } elseif ($status -eq "READY") {
                    Write-Info "提交匯入（commit）..."
                    $commitResp = curl.exe -s -X POST @headers "http://localhost:18002/api/v2/import/jobs/$jobId/commit"
                    Write-Host "commit 回應: $commitResp"
                    Write-Success "v2 匯入測試完成"
                } else {
                    Write-Warning "等待逾時：job 尚未 READY/FAILED，請稍後到 UI 或 API 查詢狀態。"
                }
            } else {
                Write-Warning "無法解析 job_id，跳過後續測試"
            }
        }
        
    } catch {
        Write-Error "檔案上傳測試失敗: $_"
    }

    # 清理臨時文件（若是 fallback 產生的 temp 檔）
    try {
        if ($testCsvPath -and $testCsvPath -like "*\\Temp\\P1_2503033_01.csv") {
            Remove-Item $testCsvPath -ErrorAction SilentlyContinue
        }
    } catch {}
}

Write-Host ""
Write-ColorOutput Blue @"
 前端訪問資訊
================
"@
Write-Success "前端應用已啟動: http://localhost:18003"
Write-Success "後端 API 文件: http://localhost:18002/docs"
Write-Success "後端 API Redoc: http://localhost:18002/redoc"

Write-Host ""
Write-ColorOutput Blue @"
 環境配置說明
================
"@
Write-Host "• API Base URL: 在 .env 文件中配置 VITE_API_URL"
Write-Host "• 檔案大小限制: 在 .env 文件中配置 VITE_MAX_FILE_SIZE"
Write-Host "• CORS 設定: 在 .env 文件中配置 CORS_ORIGINS"
Write-Host ""
Write-Host " vite.config.ts 代理設定已配置 /api 路徑到後端"
Write-Host ""

Write-ColorOutput Blue @"
 容器狀態
===========
"@
docker compose ps

Write-Host ""
Write-Success " 一鍵啟動與驗證完成！"
Write-Host ""
Write-Host "使用以下命令查看日誌："
Write-Host "  docker compose logs -f backend    # 後端日誌"
Write-Host "  docker compose logs -f frontend   # 前端日誌"
Write-Host "  docker compose logs -f db         # 資料庫日誌"
Write-Host ""
Write-Host "停止服務："
Write-Host "  docker compose down"
Write-Host ""
Write-Host "停止並清理資料："
Write-Host "  docker compose down -v"
Write-Host ""

# 自動打開瀏覽器（可選）
$openBrowser = Read-Host "是否自動打開前端頁面？(y/N)"
if ($openBrowser -eq 'y' -or $openBrowser -eq 'Y') {
    Start-Process "http://localhost:18003"
}
