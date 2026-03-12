@echo off
chcp 65001 >nul 2>&1
setlocal

echo.
echo ========================================
echo         Demo Stop (env.demo)
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

set "DOCKER_COMPOSE=docker-compose"
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker Compose is not available.
        pause
        exit /b 1
    ) else (
        set "DOCKER_COMPOSE=docker compose"
    )
)

cd /d "%SERVER_PATH%"
%DOCKER_COMPOSE% --env-file .env.demo down --remove-orphans
if errorlevel 1 (
    echo [WARN] Stop command returned non-zero. Please check docker logs.
) else (
    echo Demo services stopped.
)

echo.
echo Press any key to exit...
pause >nul
