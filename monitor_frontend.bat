@echo off 
chcp 65001 > nul 
title 表單分析系統 - 前端日誌監控 
cd /d "C:\Users\Yucheng\Desktop\form-analysis-sepc-kit\form-analysis-server" 
echo ======================================== 
echo     前端應用日誌監控 
echo ======================================== 
echo 前端應用 URL: http://localhost:5173 
echo ======================================== 
echo. 
docker-compose logs -f frontend 
