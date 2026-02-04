@echo off
chcp 65001 > nul
echo.
echo ========================================
echo     表單分析系統 - 停止與清理腳本
echo ========================================
echo.

cd /d "%~dp0"
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

REM Compose v1/v2 偵測
set "DOCKER_COMPOSE=docker-compose"
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose --version >nul 2>&1
    if errorlevel 1 (
        echo Docker Compose 未安裝或不可用
        echo   請確認 Docker Desktop 已安裝 compose plugin 或已安裝 docker-compose
        pause
        exit /b 1
    ) else (
        set "DOCKER_COMPOSE=docker compose"
    )
)

echo [1/3] 停止所有服務...
cd "%SERVER_PATH%"
%DOCKER_COMPOSE% down --remove-orphans
if not errorlevel 1 (
    echo  所有服務已停止
) else (
    echo   停止服務時遇到問題
)

echo.
echo [2/3] 清理監控腳本...
if exist "%PROJECT_ROOT%\monitor_backend.bat" (
    del "%PROJECT_ROOT%\monitor_backend.bat"
    echo  已清理後端監控腳本
)
if exist "%PROJECT_ROOT%\monitor_frontend.bat" (
    del "%PROJECT_ROOT%\monitor_frontend.bat"
    echo  已清理前端監控腳本
)

echo.
echo [3/3] 檢查服務狀態...
%DOCKER_COMPOSE% ps

echo.
echo ========================================
echo             清理完成
echo ========================================
echo.
echo 所有服務已停止，監控腳本已清理
echo 要重新啟動系統，請執行: start-system.bat
echo.
pause