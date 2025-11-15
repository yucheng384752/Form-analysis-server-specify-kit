@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
echo.
echo ========================================
echo     表單分析系統 - 簡化啟動腳本
echo ========================================
echo.

REM 設置工作目錄
cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

echo 項目路徑: %PROJECT_ROOT%
echo 服務器路徑: %SERVER_PATH%
echo.

REM 檢查 Docker Desktop 是否正在運行
echo [1] 檢查 Docker Desktop...
docker ps >nul 2>&1
if errorlevel 1 (
    echo Docker Desktop 未啟動或無法連接
    echo.
    echo 請執行以下步驟：
    echo 1. 手動開啟 Docker Desktop 應用程序
    echo 2. 等待 Docker Desktop 完全啟動 (通常需要 30-60 秒)
    echo 3. 確認系統托盤中的 Docker 圖標不再旋轉
    echo 4. 重新執行此腳本
    echo.
    pause
    exit /b 1
) else (
    echo  Docker 服務正常運行
)

REM 檢查 docker-compose 檔案
echo [2] 檢查配置檔案...
if not exist "%SERVER_PATH%\docker-compose.yml" (
    echo 找不到 docker-compose.yml 檔案
    echo 預期路徑: %SERVER_PATH%\docker-compose.yml
    pause
    exit /b 1
) else (
    echo  找到 docker-compose.yml
)

REM 切換到服務器目錄
cd /d "%SERVER_PATH%"

echo [3] 停止現有容器...
docker-compose down --remove-orphans --volumes

echo.
echo [4] 啟動服務...
docker-compose up -d --build

if errorlevel 1 (
    echo 服務啟動失敗
    echo.
    echo 查看詳細日誌:
    docker-compose logs --tail=20
    pause
    exit /b 1
)

echo.
echo [5] 等待服務啟動...
timeout /t 10 /nobreak >nul

echo.
echo  服務啟動完成！
echo.
echo 服務連結：
echo 前端: http://localhost:5173
echo API: http://localhost:8000/docs
echo.
echo 當前容器狀態：
docker-compose ps

echo.
echo 按任意鍵結束...
pause >nul