@echo off
chcp 65001 > nul
echo.
echo ========================================
echo         前端後端連接診斷工具
echo ========================================
echo.

echo [1] 檢查所有服務狀態...
docker-compose -f "c:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\docker-compose.yml" ps
echo.

echo [2] 測試後端 API 健康檢查...
PowerShell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/healthz' -UseBasicParsing; Write-Host ' 後端健康檢查成功 - 狀態碼:' $response.StatusCode; Write-Host '   回應:' $response.Content } catch { Write-Host ' 後端健康檢查失敗:' $_.Exception.Message }"
echo.

echo [3] 測試日誌 API 端點...
PowerShell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/logs/files' -UseBasicParsing; Write-Host ' 日誌 API 成功 - 狀態碼:' $response.StatusCode; $json = $response.Content | ConvertFrom-Json; Write-Host '   找到' $json.files.Count '個日誌檔案' } catch { Write-Host ' 日誌 API 失敗:' $_.Exception.Message }"
echo.

echo [4] 測試前端應用連接...
PowerShell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing; Write-Host ' 前端應用成功 - 狀態碼:' $response.StatusCode } catch { Write-Host ' 前端應用失敗:' $_.Exception.Message }"
echo.

echo [5] 檢查前端容器環境變數...
docker exec form_analysis_frontend env | findstr VITE_API_URL
echo.

echo [6] 檢查後端容器日誌（最後5行）...
docker-compose -f "c:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\docker-compose.yml" logs backend --tail=5
echo.

echo [7] 檢查前端容器日誌（最後5行）...
docker-compose -f "c:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server\docker-compose.yml" logs frontend --tail=5
echo.

echo ========================================
echo           診斷完成
echo ========================================
echo.
echo  如果仍有問題，請嘗試：
echo    1. 清除瀏覽器緩存並硬重新整理 (Ctrl+Shift+R)
echo    2. 在開發者工具中檢查網路請求
echo    3. 確認防火牆或防毒軟體未阻擋連接
echo.
pause