@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
echo.
echo ========================================
echo     表單分析系統 - 單獨啟動後端
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

set "HOST_API_PORT=18002"
if exist "%SERVER_PATH%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"API_PORT=" "%SERVER_PATH%\.env"`) do (
        if not "%%b"=="" set "HOST_API_PORT=%%b"
    )
)

echo [1/2] 啟動 db + backend...
cd /d "%SERVER_PATH%"
%DOCKER_COMPOSE% up -d --build db backend
if errorlevel 1 (
    echo 啟動失敗，請查看日誌：
    echo   monitor_backend.bat
    pause
    exit /b 1
)

echo.
echo [2/2] 完成
echo 後端 URL: http://localhost:!HOST_API_PORT!
echo API Docs: http://localhost:!HOST_API_PORT!/docs
echo.
echo 觀看日誌：monitor_backend.bat
echo.
pause
