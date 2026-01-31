@echo off
setlocal

REM NOTE: This .bat is an ASCII launcher to avoid cmd.exe encoding issues.
REM The real logic lives in quick-start.ps1.

set "PS_ARGS="

:parse
if "%~1"=="" goto run

if /I "%~1"=="--reset-db" (
	set "PS_ARGS=%PS_ARGS% -ResetDb"
	shift
	goto parse
)

if /I "%~1"=="--skip-tests" (
	set "PS_ARGS=%PS_ARGS% -SkipTests"
	shift
	goto parse
)

if /I "%~1"=="--help" (
	set "PS_ARGS=%PS_ARGS% -Help"
	shift
	goto parse
)

REM Pass-through any other args
set "PS_ARGS=%PS_ARGS% %~1"
shift
goto parse

:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0quick-start.ps1" %PS_ARGS%
exit /b %errorlevel%