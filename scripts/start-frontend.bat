@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
echo.
echo ========================================
echo     表單分析系統 - 單獨啟動前端
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

if not exist "%SERVER_PATH%\docker-compose.yml" (
    echo 找不到 docker-compose.yml: %SERVER_PATH%\docker-compose.yml
    pause
    exit /b 1
)

docker --version >nul 2>&1
if errorlevel 1 (
    echo Docker 未安裝或未啟動，請先啟動 Docker Desktop
    pause
    exit /b 1
)

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

set "HOST_FE_PORT=18003"
if exist "%SERVER_PATH%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"FRONTEND_PORT=" "%SERVER_PATH%\.env"`) do (
        if not "%%b"=="" set "HOST_FE_PORT=%%b"
    )
)

echo [1/1] 啟動 frontend...
cd /d "%SERVER_PATH%"
%DOCKER_COMPOSE% up -d --build frontend
if errorlevel 1 (
    echo 啟動失敗，請查看日誌：
    echo   monitor_frontend.bat
    pause
    exit /b 1
)

echo.
echo     檢查前端依賴（node_modules volume）...
docker exec form_analysis_frontend sh -lc "test -f node_modules/.package-lock.json || npm ci --silent" >nul 2>&1
%DOCKER_COMPOSE% restart frontend >nul 2>&1

echo.
echo 完成
echo 前端 URL: http://localhost:!HOST_FE_PORT!/index.html
echo.
echo 觀看日誌：monitor_frontend.bat
echo.
pause
