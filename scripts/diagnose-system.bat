@echo off
chcp 65001 > nul
echo.
echo ========================================
echo     表單分析系統 - 診斷工具
echo ========================================
echo.

cd /d "%~dp0"
set "PROJECT_ROOT=%cd%"
set "SERVER_PATH=%PROJECT_ROOT%\form-analysis-server"

echo [1/8] Docker 服務檢查...
docker --version 2>&1
if errorlevel 1 (
    echo ❌ Docker 未安裝或未啟動
    goto end_diagnosis
) else (
    echo ✅ Docker 服務可用
)

echo.
echo [2/8] Docker Compose 檢查...
docker-compose --version 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose 未安裝
    goto end_diagnosis
) else (
    echo ✅ Docker Compose 可用
)

echo.
echo [3/8] 端口佔用檢查...
echo 檢查關鍵端口狀態：
netstat -an | find ":5432" 2>&1
if not errorlevel 1 (
    echo ⚠️  端口 5432 已佔用
) else (
    echo ✅ 端口 5432 可用
)

netstat -an | find ":8000" 2>&1
if not errorlevel 1 (
    echo ⚠️  端口 8000 已佔用
) else (
    echo ✅ 端口 8000 可用
)

netstat -an | find ":5173" 2>&1
if not errorlevel 1 (
    echo ⚠️  端口 5173 已佔用
) else (
    echo ✅ 端口 5173 可用
)

echo.
echo [4/8] 容器狀態檢查...
cd "%SERVER_PATH%"
echo 目前容器狀態：
docker-compose ps 2>&1
if errorlevel 1 (
    echo ❌ 無法取得容器狀態
) else (
    echo ✅ 容器狀態檢查完成
)

echo.
echo [5/8] Docker 映像檔檢查...
echo 檢查必要的映像檔：
docker images | find "postgres" 2>&1
docker images | find "form-analysis-server"  2>&1

echo.
echo [6/8] 資料卷檢查...
echo 檢查 Docker 資料卷：
docker volume ls | find "postgres_data" 2>&1
docker volume ls | find "upload_data" 2>&1

echo.
echo [7/8] 網路檢查...
echo 檢查 Docker 網路：
docker network ls | find "app-network" 2>&1

echo.
echo [8/8] 日誌檢查...
echo 如果容器存在，顯示最近日誌：
docker-compose logs --tail=10 db 2>&1
echo ----------------------------------------
docker-compose logs --tail=10 backend 2>&1
echo ----------------------------------------
docker-compose logs --tail=10 frontend 2>&1

:end_diagnosis
echo.
echo ========================================
echo            診斷完成
echo ========================================
echo.
echo 🔧 常用修復指令：
echo    清理所有資源: docker-compose down -v --remove-orphans
echo    重建映像檔: docker-compose build --no-cache
echo    強制重新下載: docker-compose pull
echo    檢查 Docker 磁碟空間: docker system df
echo    清理未使用資源: docker system prune
echo.
echo 📞 如果問題持續，請提供以上診斷資訊尋求協助
echo.
pause