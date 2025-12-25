@echo off
chcp 65001 >nul
echo ════════════════════════════════════════
echo            專案打包準備
echo ════════════════════════════════════════
echo.

echo   此腳本將清理專案以便打包部署
echo    將會刪除以下內容：
echo    - Python 虛擬環境 (.venv)
echo    - Node.js 模組 (node_modules)
echo    - Python 快取檔案 (__pycache__)
echo    - Vite 快取檔案 (.vite)
echo    - 上傳檔案 (uploads 內容)
echo    - Docker 容器和映像
echo.

set /p confirm="是否繼續？(y/N): "
if /i not "%confirm%"=="y" (
    echo 已取消操作
    pause
    exit /b 0
)

echo.
echo [1/7] 停止 Docker 服務...
call scripts\stop-system.bat >nul 2>&1
echo  Docker 服務已停止

echo.
echo [2/7] 清理 Docker 資源...
cd form-analysis-server
docker-compose down --volumes >nul 2>&1
docker system prune -f >nul 2>&1
cd ..
echo  Docker 資源已清理

echo.
echo [3/7] 清理 Python 虛擬環境...
if exist ".venv" (
    rmdir /s /q ".venv" >nul 2>&1
    echo  .venv 已刪除
)

if exist "__pycache__" (
    rmdir /s /q "__pycache__" >nul 2>&1
    echo  __pycache__ 已刪除
)

echo.
echo [4/7] 清理前端依賴...
if exist "form-analysis-server\frontend\node_modules" (
    rmdir /s /q "form-analysis-server\frontend\node_modules" >nul 2>&1
    echo  node_modules 已刪除
)

if exist "form-analysis-server\frontend\.vite" (
    rmdir /s /q "form-analysis-server\frontend\.vite" >nul 2>&1
    echo  .vite 快取已刪除
)

if exist ".vite" (
    rmdir /s /q ".vite" >nul 2>&1
    echo  根目錄 .vite 已刪除
)

echo.
echo [5/7] 清理後端快取...
cd form-analysis-server\backend
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" >nul 2>&1
cd ..\..
echo  後端 __pycache__ 已清理

echo.
echo [6/7] 清理上傳檔案...
if exist "uploads" (
    for /f %%f in ('dir /b uploads 2^>nul') do (
        if not "%%f"==".gitkeep" (
            del /q "uploads\%%f" >nul 2>&1
        )
    )
    echo  uploads 內容已清理（保留 .gitkeep）
)

echo.
echo [7/7] 檢查專案大小...
echo  專案統計：
for /f "tokens=3" %%a in ('dir /s /-c ^| find "個檔案"') do set files=%%a
for /f "tokens=3" %%a in ('dir /s /-c ^| find "位元組"') do set bytes=%%a
echo    檔案數量: %files%
echo    總大小: %bytes% 位元組

echo.
echo ════════════════════════════════════════
echo            打包準備完成！
echo ════════════════════════════════════════
echo.
echo  下一步打包選項：
echo.
echo  方式一：壓縮檔案
echo    1. 使用 WinRAR/7-Zip 壓縮整個資料夾
echo    2. 排除 .git 資料夾（如不需要版本記錄）
echo.
echo  方式二：PowerShell 壓縮
echo    Compress-Archive -Path "." -DestinationPath "..\form-analysis-kit.zip"
echo.
echo 方式三：Git 倉庫
echo    git add .
echo    git commit -m "Ready for deployment"
echo    git push origin main
echo.
echo 部署說明：
echo    - 目標電腦請參考 DEPLOYMENT_GUIDE.md
echo    - 首次部署執行 verify-deployment.bat
echo    - 使用 scripts\start-system.bat 啟動
echo.
pause