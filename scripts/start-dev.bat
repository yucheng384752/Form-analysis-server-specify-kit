@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: Development Environment Startup Script (start-dev.bat)
:: ============================================================================
:: Optimized first-time setup + daily startup script.
:: Automatically creates .env.dev if missing, validates prerequisites,
:: checks port availability, and uses smart build detection.
::
:: Usage:
::   .\start-dev.bat               Normal startup (skip build if images exist)
::   .\start-dev.bat --build       Force rebuild images
::   .\start-dev.bat --reset-db    Remove DB volume and start fresh
::   .\start-dev.bat --no-pause    Non-interactive mode (CI)
:: ============================================================================

set "PAUSE_ON_EXIT=1"
set "FORCE_BUILD=0"
set "RESET_DB=0"

:parse_args
if "%~1"=="" goto done_args
if /I "%~1"=="--no-pause" set "PAUSE_ON_EXIT=0"
if /I "%~1"=="--build"    set "FORCE_BUILD=1"
if /I "%~1"=="--reset-db" set "RESET_DB=1"
shift
goto parse_args
:done_args

if /I "%CI%"=="true" set "PAUSE_ON_EXIT=0"
if /I "%CI%"=="1" set "PAUSE_ON_EXIT=0"
if /I "%GITHUB_ACTIONS%"=="true" set "PAUSE_ON_EXIT=0"

echo.
echo ========================================
echo    Development Startup (env.dev)
echo ========================================
echo.

:: ── Phase 0: Resolve paths ─────────────────────────────────────────────────
cd /d "%~dp0"
cd ..
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"
set "ENV_FILE=%SERVER_PATH%\.env.dev"
set "ENV_EXAMPLE=%SERVER_PATH%\.env.example"
set "COMPOSE_FILE=%SERVER_PATH%\docker-compose.yml"

:: ── Phase 1: Pre-flight checks ─────────────────────────────────────────────
echo [1/6] Pre-flight checks...

:: 1a. Docker daemon
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running.
    echo   Please start Docker Desktop and try again.
    call :maybe_pause
    exit /b 1
)
echo   - Docker daemon: OK

:: 1b. Docker Compose
set "DOCKER_COMPOSE=docker-compose"
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker Compose is not available.
        echo   Install Docker Desktop (includes Compose) or install docker-compose separately.
        call :maybe_pause
        exit /b 1
    ) else (
        set "DOCKER_COMPOSE=docker compose"
    )
)
echo   - Docker Compose: OK

:: 1c. docker-compose.yml
if not exist "%COMPOSE_FILE%" (
    echo [ERROR] Missing %COMPOSE_FILE%
    call :maybe_pause
    exit /b 1
)
echo   - docker-compose.yml: OK

:: ── Phase 2: Auto-setup .env.dev ────────────────────────────────────────────
if not exist "%ENV_FILE%" (
    echo.
    echo [2/6] First-time setup: generating .env.dev ...
    if not exist "%ENV_EXAMPLE%" (
        echo [ERROR] Missing %ENV_EXAMPLE% — cannot generate .env.dev.
        call :maybe_pause
        exit /b 1
    )
    call :generate_env_dev
    echo   - .env.dev created from .env.example with dev defaults.
    echo   - Review %ENV_FILE% if you need to customise settings.
) else (
    echo [2/6] .env.dev: OK
)

:: Ensure external placeholder dirs exist so Docker volume mounts don't fail
if not exist "%SERVER_PATH%\.external\september_v2" mkdir "%SERVER_PATH%\.external\september_v2" >nul 2>&1
if not exist "%SERVER_PATH%\.external\Analytical-Four" mkdir "%SERVER_PATH%\.external\Analytical-Four" >nul 2>&1

:: ── Phase 3: Read ports ^& check availability ───────────────────────────────
echo [3/6] Checking port availability...
set "HOST_API_PORT=18002"
set "HOST_FRONTEND_PORT=18003"
set "HOST_DB_PORT=18001"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"HOST_API_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_API_PORT=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"FRONTEND_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_FRONTEND_PORT=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"POSTGRES_PORT=" "%ENV_FILE%"`) do if not "%%b"=="" set "HOST_DB_PORT=%%b"

set "PORT_CONFLICT=0"
for %%p in (!HOST_DB_PORT! !HOST_API_PORT! !HOST_FRONTEND_PORT!) do (
    netstat -an | findstr "LISTENING" | findstr ":%%p " >nul 2>&1
    if not errorlevel 1 (
        :: Check if the process is our own Docker container (allow re-start)
        docker ps --format "{{.Ports}}" 2>nul | findstr ":%%p->" >nul 2>&1
        if errorlevel 1 (
            echo   [WARN] Port %%p is already in use by another process.
            set "PORT_CONFLICT=1"
        ) else (
            echo   - Port %%p: in use by existing dev container (will be replaced^)
        )
    ) else (
        echo   - Port %%p: available
    )
)
if "!PORT_CONFLICT!"=="1" (
    echo.
    echo   Some ports are occupied by non-Docker processes.
    echo   Either free these ports or change them in %ENV_FILE%.
    echo   Continuing anyway — Docker may fail to bind...
    echo.
)

:: ── Phase 3b: Ensure external placeholder dirs exist ────────────────────────
:: If the user hasn't set external analytics paths, create empty placeholders
:: so Docker volume mounts don't fail.
set "SEP_V2_PATH="
set "AN4_PATH="
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"SEPTEMBER_V2_HOST_PATH=" "%ENV_FILE%"`) do if not "%%b"=="" set "SEP_V2_PATH=%%b"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"ANALYTICAL_FOUR_HOST_PATH=" "%ENV_FILE%"`) do if not "%%b"=="" set "AN4_PATH=%%b"

if defined SEP_V2_PATH (
    if not exist "!SEP_V2_PATH!" (
        echo   [INFO] External path !SEP_V2_PATH! not found — analytics features may be unavailable.
    )
)
if defined AN4_PATH (
    if not exist "!AN4_PATH!" (
        echo   [INFO] External path !AN4_PATH! not found — analytics features may be unavailable.
    )
)

:: ── Phase 4: Stop old containers ────────────────────────────────────────────
echo.
echo [4/6] Stopping existing dev containers...
cd /d "%SERVER_PATH%"

if "!RESET_DB!"=="1" (
    echo   (--reset-db) Removing containers AND volumes...
    %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev down --remove-orphans -v
) else (
    %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev down --remove-orphans
)

:: ── Phase 5: Build ^& Start ─────────────────────────────────────────────────
echo.
if "!FORCE_BUILD!"=="1" (
    echo [5/6] Starting dev stack (force rebuild)...
    %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev up -d --build
) else (
    :: Smart build: only use --build if no images exist yet
    set "NEEDS_BUILD=0"
    docker images -q form-analysis-dev-backend 2>nul | findstr . >nul 2>&1
    if errorlevel 1 set "NEEDS_BUILD=1"
    docker images -q form-analysis-dev-frontend 2>nul | findstr . >nul 2>&1
    if errorlevel 1 set "NEEDS_BUILD=1"

    if "!NEEDS_BUILD!"=="1" (
        echo [5/6] Starting dev stack (first build — this may take a few minutes)...
        %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev up -d --build
    ) else (
        echo [5/6] Starting dev stack (images exist, skipping rebuild)...
        echo   Tip: use --build flag to force rebuild if code changed.
        %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev up -d
    )
)

if errorlevel 1 (
    echo.
    echo [ERROR] Dev stack failed to start. Last logs:
    echo ────────────────────────────────────────
    %DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev logs --tail=40
    echo ────────────────────────────────────────
    echo.
    echo Common causes:
    echo   - Port conflict (check ports !HOST_DB_PORT!, !HOST_API_PORT!, !HOST_FRONTEND_PORT!)
    echo   - Docker out of disk space (run: docker system df)
    echo   - Dockerfile syntax error (run with --build to see details)
    call :maybe_pause
    exit /b 1
)

:: ── Phase 6: Health checks with retry ───────────────────────────────────────
echo.
echo [6/6] Health checks (waiting for services)...
%DOCKER_COMPOSE% -p form-analysis-dev --env-file .env.dev ps

:: Backend health check (up to 60s)
set "BACKEND_OK=0"
for /L %%i in (1,1,12) do (
    if "!BACKEND_OK!"=="0" (
        timeout /t 5 /nobreak >nul
        curl -4 -sf http://127.0.0.1:!HOST_API_PORT!/healthz >nul 2>&1
        if not errorlevel 1 (
            set "BACKEND_OK=1"
        ) else (
            <nul set /p ="."
        )
    )
)
echo.
if "!BACKEND_OK!"=="1" (
    echo   - Backend healthz: OK
) else (
    echo   - Backend healthz: not ready after 60s
    echo     Check logs: docker logs form_analysis_api
)

:: Frontend health check (up to 30s)
set "FRONTEND_OK=0"
for /L %%i in (1,1,6) do (
    if "!FRONTEND_OK!"=="0" (
        timeout /t 5 /nobreak >nul
        curl -4 -sf http://127.0.0.1:!HOST_FRONTEND_PORT! >nul 2>&1
        if not errorlevel 1 (
            set "FRONTEND_OK=1"
        ) else (
            <nul set /p ="."
        )
    )
)
echo.
if "!FRONTEND_OK!"=="1" (
    echo   - Frontend: OK
) else (
    echo   - Frontend: not ready after 30s
    echo     Check logs: docker logs form_analysis_frontend
)

:: ── Summary ─────────────────────────────────────────────────────────────────
echo.
echo ========================================
echo   Development Environment Ready
echo ========================================
echo.
echo   Frontend:   http://127.0.0.1:!HOST_FRONTEND_PORT!
echo   Backend:    http://127.0.0.1:!HOST_API_PORT!
echo   API Docs:   http://127.0.0.1:!HOST_API_PORT!/docs
echo   PostgreSQL: 127.0.0.1:!HOST_DB_PORT!
echo.
echo   Source code is mounted — changes will hot reload.
echo   Stop with:  scripts\stop-dev.bat
echo.

call :maybe_pause
exit /b 0

:: ============================================================================
:: Subroutines
:: ============================================================================

:maybe_pause
if "!PAUSE_ON_EXIT!"=="1" (
    echo Press any key to exit...
    pause >nul
)
exit /b 0

:generate_env_dev
:: Generate a sensible .env.dev from .env.example with dev-friendly defaults.
:: We copy .env.example then patch the lines that need dev values.
copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul

:: Apply dev-specific overrides using PowerShell for reliable text replacement
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$f = '%ENV_FILE%';" ^
  "$c = Get-Content $f -Raw -Encoding UTF8;" ^
  "$c = $c -replace '(?m)^POSTGRES_PASSWORD=.*$', 'POSTGRES_PASSWORD=dev-change-me-strong';" ^
  "$c = $c -replace '(?m)^POSTGRES_DB=.*$', 'POSTGRES_DB=form_analysis_dev_db';" ^
  "$c = $c -replace '(?m)^DATABASE_URL=.*$', 'DATABASE_URL=postgresql+psycopg://app:dev-change-me-strong@db:5432/form_analysis_dev_db';" ^
  "$c = $c -replace '(?m)^LOG_LEVEL=.*$', 'LOG_LEVEL=DEBUG';" ^
  "$c = $c -replace '(?m)^DEBUG=.*$', 'DEBUG=true';" ^
  "$c = $c -replace '(?m)^RELOAD=.*$', 'RELOAD=true';" ^
  "$c = $c -replace '(?m)^#ADMIN_API_KEYS=.*$', 'ADMIN_API_KEYS=dev-admin-key-for-testing';" ^
  "$c = $c -replace '(?m)^#ADMIN_API_KEY_HEADER=.*$', 'ADMIN_API_KEY_HEADER=X-Admin-API-Key';" ^
  "$c = $c -replace '(?m)^SECRET_KEY=.*$', 'SECRET_KEY=dev-secret-key-at-least-32-characters-long';" ^
  "$c = $c -replace '(?m)^ENVIRONMENT=.*$', 'ENVIRONMENT=development';" ^
  "Set-Content $f $c -Encoding UTF8 -NoNewline"

echo   Applied dev-friendly defaults (DEBUG, RELOAD, dev DB credentials).
exit /b 0
