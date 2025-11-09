@echo off
chcp 65001 >nul
echo ════════════════════════════════════════
echo           📋 專案部署驗證
echo ════════════════════════════════════════
echo.

echo [1/6] 檢查 Docker 安裝...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 未安裝或未運行
    echo    請先安裝 Docker Desktop
    pause
    exit /b 1
) else (
    echo ✅ Docker 已安裝
)

echo.
echo [2/6] 檢查 Docker Compose...
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose 未安裝
    pause
    exit /b 1
) else (
    echo ✅ Docker Compose 已安裝
)

echo.
echo [3/6] 檢查專案結構...
if not exist "scripts\start-system.bat" (
    echo ❌ 啟動腳本不存在: scripts\start-system.bat
    pause
    exit /b 1
)

if not exist "form-analysis-server\docker-compose.yml" (
    echo ❌ Docker 配置檔案不存在: form-analysis-server\docker-compose.yml
    pause
    exit /b 1
)

if not exist "form-analysis-server\backend" (
    echo ❌ 後端目錄不存在: form-analysis-server\backend
    pause
    exit /b 1
)

if not exist "form-analysis-server\frontend" (
    echo ❌ 前端目錄不存在: form-analysis-server\frontend
    pause
    exit /b 1
)

echo ✅ 專案結構完整

echo.
echo [4/6] 檢查測試資料...
if not exist "test-data" (
    echo ⚠️  測試資料目錄不存在，建議重新解壓
) else (
    echo ✅ 測試資料完整
)

echo.
echo [5/6] 檢查 Docker 服務...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 服務未運行
    echo    請啟動 Docker Desktop
    pause
    exit /b 1
) else (
    echo ✅ Docker 服務正常
)

echo.
echo [6/6] 檢查端口佔用...
netstat -ano | findstr :5173 >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  端口 5173 (前端) 已被佔用
)

netstat -ano | findstr :8000 >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  端口 8000 (後端) 已被佔用
)

netstat -ano | findstr :5432 >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  端口 5432 (資料庫) 已被佔用
)

echo ✅ 端口檢查完成

echo.
echo ════════════════════════════════════════
echo           🎉 部署驗證完成！
echo ════════════════════════════════════════
echo.
echo 📋 下一步：
echo    1. 執行: .\scripts\start-system.bat
echo    2. 開啟瀏覽器: http://localhost:5173
echo    3. 測試上傳功能和查詢功能
echo.
echo 📞 如有問題，請參考 DEPLOYMENT_GUIDE.md
echo.
pause