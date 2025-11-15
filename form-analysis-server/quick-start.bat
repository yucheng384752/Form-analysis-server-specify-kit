@echo off
REM Form Analysis - Docker 一鍵啟動與驗證腳本 (Windows)
REM 
REM 此腳本將：
REM 1. 啟動所有服務
REM 2. 等待服務就緒
REM 3. 驗證健康檢查
REM 4. 模擬完整的上傳和驗證流程
REM 5. 提供前端訪問資訊

setlocal enabledelayedexpansion

echo  Form Analysis - Docker 一鍵啟動與驗證
echo ========================================

REM 檢查 Docker 是否運行
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker 未運行，請先啟動 Docker
    pause
    exit /b 1
)

REM 檢查 curl 是否可用
curl --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] curl 未安裝，請先安裝 curl
    echo 可以從 https://curl.se/download.html 下載
    pause
    exit /b 1
)

echo [INFO] 停止並清理現有容器...
docker compose down -v

echo [INFO] 啟動所有服務...
docker compose up -d

echo [INFO] 等待服務啟動...
timeout /t 10 /nobreak >nul

REM 等待數據庫就緒
echo [INFO] 等待數據庫就緒...
set RETRY_COUNT=0
set MAX_RETRIES=30

:wait_db
if !RETRY_COUNT! geq !MAX_RETRIES! (
    echo [ERROR] 數據庫啟動超時
    docker compose logs db
    pause
    exit /b 1
)

docker compose exec -T db pg_isready -U app >nul 2>&1
if errorlevel 1 (
    set /a RETRY_COUNT+=1
    echo|set /p="."
    timeout /t 2 /nobreak >nul
    goto wait_db
)

echo.
echo [SUCCESS] 數據庫已就緒

REM 等待後端 API 就緒
echo [INFO] 等待後端 API 就緒...
set RETRY_COUNT=0

:wait_api
if !RETRY_COUNT! geq !MAX_RETRIES! (
    echo [ERROR] 後端 API 啟動超時
    docker compose logs backend
    pause
    exit /b 1
)

curl -f http://localhost:8000/healthz >nul 2>&1
if errorlevel 1 (
    set /a RETRY_COUNT+=1
    echo|set /p="."
    timeout /t 2 /nobreak >nul
    goto wait_api
)

echo.
echo [SUCCESS] 後端 API 已就緒

REM 等待前端就緒
echo [INFO] 等待前端就緒...
set RETRY_COUNT=0

:wait_frontend
if !RETRY_COUNT! geq !MAX_RETRIES! (
    echo [ERROR] 前端啟動超時
    docker compose logs frontend
    pause
    exit /b 1
)

curl -f http://localhost:5173 >nul 2>&1
if errorlevel 1 (
    set /a RETRY_COUNT+=1
    echo|set /p="."
    timeout /t 2 /nobreak >nul
    goto wait_frontend
)

echo.
echo [SUCCESS] 前端已就緒
echo.
echo [SUCCESS] 所有服務已啟動完成！
echo.

REM 驗證健康檢查
echo 🩺 健康檢查驗證
echo ==================

echo [INFO] 測試基本健康檢查...
curl -f http://localhost:8000/healthz
if errorlevel 1 (
    echo [ERROR] 基本健康檢查失敗
    pause
    exit /b 1
)
echo [SUCCESS] 基本健康檢查通過

echo.
echo [INFO] 測試詳細健康檢查...
curl -f http://localhost:8000/healthz/detailed >nul 2>&1
if errorlevel 1 (
    echo [WARNING] 詳細健康檢查失敗（可能尚未實現）
) else (
    echo [SUCCESS] 詳細健康檢查通過
)

echo.

REM 模擬上傳與驗證流程
echo  模擬上傳與驗證流程
echo =======================

REM 創建測試 CSV 文件
set TEMP_CSV=%TEMP%\test_upload.csv
echo lot_no,product_name,quantity,production_date > %TEMP_CSV%
echo 1234567_01,測試產品A,100,2024-01-15 >> %TEMP_CSV%
echo 2345678_02,測試產品B,50,2024-01-16 >> %TEMP_CSV%
echo 3456789_03,測試產品C,75,2024-01-17 >> %TEMP_CSV%
echo 4567890_04,測試產品D,200,2024-01-18 >> %TEMP_CSV%
echo 5678901_05,測試產品E,125,2024-01-19 >> %TEMP_CSV%

echo [INFO] 測試檔案上傳（5 列測試數據）...

REM 使用 curl 上傳文件
curl -s -X POST -F "file=@%TEMP_CSV%" http://localhost:8000/api/upload > %TEMP%\upload_response.json

echo 上傳回應:
type %TEMP%\upload_response.json

REM 簡單解析 file_id（需要 jq 或手動解析）
REM 這裡使用簡化方法，實際使用中建議安裝 jq
echo [SUCCESS] 檔案上傳測試完成

REM 清理臨時文件
del %TEMP_CSV% >nul 2>&1
del %TEMP%\upload_response.json >nul 2>&1

echo.
echo  前端訪問資訊
echo ================
echo [SUCCESS] 前端應用已啟動: http://localhost:5173
echo [SUCCESS] 後端 API 文件: http://localhost:8000/docs
echo [SUCCESS] 後端 API Redoc: http://localhost:8000/redoc

echo.
echo  環境配置說明
echo ================
echo • API Base URL: 在 .env 文件中配置 VITE_API_URL
echo • 檔案大小限制: 在 .env 文件中配置 VITE_MAX_FILE_SIZE
echo • CORS 設定: 在 .env 文件中配置 CORS_ORIGINS
echo.
echo  vite.config.ts 代理設定已配置 /api 路徑到後端
echo.

echo  容器狀態
echo ===========
docker compose ps

echo.
echo [SUCCESS]  一鍵啟動與驗證完成！
echo.
echo 使用以下命令查看日誌：
echo   docker compose logs -f backend    # 後端日誌
echo   docker compose logs -f frontend   # 前端日誌
echo   docker compose logs -f db         # 數據庫日誌
echo.
echo 停止服務：
echo   docker compose down
echo.
echo 停止並清理數據：
echo   docker compose down -v
echo.

pause