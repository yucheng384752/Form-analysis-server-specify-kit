@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

set "PAUSE_ON_EXIT=1"
if /I "%~1"=="--no-pause" set "PAUSE_ON_EXIT=0"
if /I "%CI%"=="true" set "PAUSE_ON_EXIT=0"
if /I "%CI%"=="1" set "PAUSE_ON_EXIT=0"
if /I "%GITHUB_ACTIONS%"=="true" set "PAUSE_ON_EXIT=0"

echo.
echo ========================================
echo    Demo Startup (Stable Environment)
echo ========================================
echo.

cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"
set "ENV_FILE=%SERVER_PATH%\.env.demo"
set "COMPOSE_FILE=%SERVER_PATH%\docker-compose.demo.yml"

if not exist "%ENV_FILE%" (
    echo [ERROR] Missing %ENV_FILE%
    echo Please create it first. Copy .env.example to .env.demo and fill required values.
    call :maybe_pause
    exit /b 1
)

if not exist "%COMPOSE_FILE%" (
    echo [ERROR] Missing %COMPOSE_FILE%
    echo Please ensure docker-compose.demo.yml exists.
    call :maybe_pause
    exit /b 1
)

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

set "HOST_API_PORT=18102"
set "HOST_FRONTEND_PORT=18103"
set "HOST_DB_PORT=18101"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"HOST_API_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_API_PORT=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"FRONTEND_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_FRONTEND_PORT=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_DB_PORT=%%b"

echo [1/5] Stopping existing demo containers...
cd /d "%SERVER_PATH%"
%DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo down --remove-orphans

echo.
echo [2/5] Starting demo stack (production images)...
%DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo up -d
if errorlevel 1 (
    echo [ERROR] Demo stack failed to start.
    echo [TIP] If images don't exist, run build-demo-images.bat first.
    %DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo logs --tail=80
    call :maybe_pause
    exit /b 1
)

echo.
echo [3/5] Service status
%DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo ps

echo.
echo [4/5] Waiting for backend health...
set HEALTH_OK=0
set HEALTH_ATTEMPT=0
:health_loop
if !HEALTH_OK!==1 goto health_done
set /a HEALTH_ATTEMPT+=1
if !HEALTH_ATTEMPT! gtr 40 goto health_done
curl -4 -s http://127.0.0.1:!HOST_API_PORT!/healthz >nul 2>&1
if not errorlevel 1 (
    set HEALTH_OK=1
    echo - Backend healthz: OK
    goto health_done
)
echo - Attempt !HEALTH_ATTEMPT!/40: waiting...
timeout /t 3 /nobreak >nul
goto health_loop
:health_done
if !HEALTH_OK!==0 (
    echo [ERROR] Backend health check timed out after 120 seconds.
    %DOCKER_COMPOSE% -p form-analysis-demo -f docker-compose.demo.yml --env-file .env.demo logs --tail=50 backend
    call :maybe_pause
    exit /b 1
)

curl -4 -s http://127.0.0.1:!HOST_FRONTEND_PORT! >nul 2>&1
if errorlevel 1 (
    echo - Frontend: not ready yet (non-blocking)
) else (
    echo - Frontend: OK
)

echo.
echo [5/5] Ensuring fixed demo accounts (manager/user)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\ensure-demo-users.ps1"
if errorlevel 1 (
    echo [ERROR] ensure-demo-users failed.
    call :maybe_pause
    exit /b 1
)

if "!PAUSE_ON_EXIT!"=="1" (
    echo.
    echo Demo links - interactive mode:
    echo - Frontend: http://localhost:!HOST_FRONTEND_PORT!/index.html
    echo - Backend API: http://localhost:!HOST_API_PORT!
    echo - API Docs: http://localhost:!HOST_API_PORT!/docs
    echo - PostgreSQL: localhost:!HOST_DB_PORT!
    echo.
    echo Press any key to exit...
)

call :maybe_pause
exit /b 0

:maybe_pause
if "!PAUSE_ON_EXIT!"=="1" pause >nul
exit /b 0

