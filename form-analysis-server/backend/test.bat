@echo off
REM Windows 測試執行批次檔
echo 🧪 Form Analysis Backend - 測試執行器 (Windows)
echo ===============================================

REM 檢查 Python 是否可用
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  Python 未安裝或未加入 PATH
    pause
    exit /b 1
)

REM 檢查虛擬環境
if not exist ".venv\Scripts\python.exe" (
    echo  虛擬環境不存在，請先運行 setup.bat
    pause
    exit /b 1
)

REM 啟用虛擬環境
call .venv\Scripts\activate.bat

REM 安裝測試依賴
echo  安裝測試依賴...
python -m pip install -r requirements-test.txt

if %errorlevel% neq 0 (
    echo  測試依賴安裝失敗
    pause
    exit /b 1
)

REM 執行測試
if "%1"=="" (
    REM 沒有參數，顯示說明
    echo.
    echo 使用方法: test.bat [模式]
    echo.
    echo 可用模式:
    echo   all       - 執行所有測試
    echo   models    - 執行模型測試
    echo   coverage  - 執行測試並生成覆蓋率報告
    echo   fast      - 快速測試
    echo.
    echo 範例:
    echo   test.bat models
    echo   test.bat coverage
    echo.
    pause
    exit /b 0
)

echo  執行測試模式: %1
python run_tests.py %1 %2 %3 %4 %5

if %errorlevel% neq 0 (
    echo  測試失敗
    pause
    exit /b 1
)

echo  測試完成
if "%1"=="coverage" (
    echo  覆蓋率報告: htmlcov\index.html
    echo 是否要開啟報告? (y/n)
    set /p choice=
    if /i "%choice%"=="y" start htmlcov\index.html
)

pause