@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo Form Analysis System - 啟動腳本
echo ============================================

REM 設定專案根目錄 (腳本所在目錄的上層)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "BACKEND_DIR=%PROJECT_ROOT%\form-analysis-server\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%\form-analysis-server\frontend"
set "ENV_FILE=%PROJECT_ROOT%\form-analysis-server\.env"

REM 服務對外端口（host）
set "HOST_API_PORT=18002"
set "HOST_FRONTEND_PORT=18003"
if exist "%ENV_FILE%" (
	for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"HOST_API_PORT=" "%ENV_FILE%"`) do (
		if not "%%b"=="" set "HOST_API_PORT=%%b"
	)
	for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /R /B /C:"FRONTEND_PORT=" "%ENV_FILE%"`) do (
		if not "%%b"=="" set "HOST_FRONTEND_PORT=%%b"
	)
)

REM 啟動後端服務
echo  正在啟動後端服務...
start "Backend API" cmd /k "cd /d "%BACKEND_DIR%" && .\venv\Scripts\activate.bat && set PYTHONPATH=. && python -c \"import sys; sys.path.insert(0, '.'); from app.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=%HOST_API_PORT%)\""

REM 等待後端啟動
echo  等待後端服務啟動...
timeout /t 5 /nobreak > nul

REM 啟動前端服務
echo  正在啟動前端服務...
start "Frontend Dev" cmd /k "cd /d "%FRONTEND_DIR%" && set VITE_API_URL=http://localhost:%HOST_API_PORT% && npm run dev -- --host 127.0.0.1 --port %HOST_FRONTEND_PORT%"

REM 等待前端啟動
echo  等待前端服務啟動...
timeout /t 5 /nobreak > nul

REM 打開瀏覽器
echo 🌍 正在打開瀏覽器...
start http://localhost:%HOST_FRONTEND_PORT%/index.html

echo.
echo  服務啟動完成！
echo  後端 API: http://localhost:%HOST_API_PORT%
echo  前端界面: http://localhost:%HOST_FRONTEND_PORT%/index.html
echo  API 文檔: http://localhost:%HOST_API_PORT%/docs
echo.
echo 關閉此窗口將不會停止服務
echo 要停止服務，請關閉對應的終端窗口
pause
