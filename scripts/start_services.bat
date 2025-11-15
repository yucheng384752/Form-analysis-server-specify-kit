@echo off
echo ============================================
echo Form Analysis System - 啟動腳本
echo ============================================

REM 啟動後端服務
echo  正在啟動後端服務...
start "Backend API" cmd /k "cd /d C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\backend && .\venv\Scripts\activate.bat && set PYTHONPATH=. && python -c \"import sys; sys.path.insert(0, '.'); from app.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8000)\""

REM 等待後端啟動
echo  等待後端服務啟動...
timeout /t 5 /nobreak > nul

REM 啟動前端服務
echo  正在啟動前端服務...
start "Frontend Dev" cmd /k "cd /d C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\frontend && npm run dev"

REM 等待前端啟動
echo  等待前端服務啟動...
timeout /t 5 /nobreak > nul

REM 打開瀏覽器
echo 🌍 正在打開瀏覽器...
start http://localhost:5173

echo.
echo  服務啟動完成！
echo  後端 API: http://localhost:8000
echo  前端界面: http://localhost:5173
echo  API 文檔: http://localhost:8000/docs
echo.
echo 關閉此窗口將不會停止服務
echo 要停止服務，請關閉對應的終端窗口
pause
