@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: Development Environment Stop Script (stop-dev.bat)
:: ============================================================================
:: Properly stops the dev stack using the correct project name.
::
:: Usage:
::   .\stop-dev.bat            Stop containers (preserve data)
::   .\stop-dev.bat --reset-db Stop containers AND remove DB volume
:: ============================================================================

set "PAUSE_ON_EXIT=1"
set "RESET_DB=0"
if /I "%~1"=="--no-pause" set "PAUSE_ON_EXIT=0"
if /I "%~1"=="--reset-db" set "RESET_DB=1"
if /I "%~2"=="--no-pause" set "PAUSE_ON_EXIT=0"
if /I "%~2"=="--reset-db" set "RESET_DB=1"

echo.
echo ========================================
echo      Dev Stop (form-analysis-dev)
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

:: Detect Docker Compose
set "DOCKER_COMPOSE=docker-compose"
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker Compose is not available.
        call :maybe_pause
        exit /b 1
    ) else (
        set "DOCKER_COMPOSE=docker compose"
    )
)

cd /d "%SERVER_PATH%"

if "!RESET_DB!"=="1" (
    echo [1/2] Stopping dev containers AND removing volumes...
    %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev down --remove-orphans -v
) else (
    echo [1/2] Stopping dev containers (data preserved)...
    %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev down --remove-orphans
)

if errorlevel 1 (
    echo [WARN] Stop command returned non-zero. Check docker logs.
) else (
    echo   Dev services stopped.
)

echo.
echo [2/2] Verifying...
%DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev ps

echo.
echo ========================================
echo   Dev environment stopped.
echo ========================================
echo.
echo   Restart with: scripts\start-dev.bat
echo.

call :maybe_pause
exit /b 0

:maybe_pause
if "!PAUSE_ON_EXIT!"=="1" (
    echo Press any key to exit...
    pause >nul
)
exit /b 0
