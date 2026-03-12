# Demo / 開發環境分離操作手冊

> 更新日期：2026-03-09

---

## 目錄

1. [架構概述](#架構概述)
2. [環境差異對照](#環境差異對照)
3. [操作步驟](#操作步驟)
   - [開發環境啟動](#開發環境啟動)
   - [Demo 環境建置與啟動](#demo-環境建置與啟動)
   - [併行執行](#併行執行)
4. [故障排除](#故障排除)
5. [常見問題 FAQ](#常見問題-faq)

---

## 架構概述

本專案支援兩套獨立運行的環境：

```
┌─────────────────────────────────────────────────────────────────┐
│                         主機                                    │
├─────────────────────────────┬───────────────────────────────────┤
│      開發環境 (Dev)         │         Demo 環境 (Stable)        │
├─────────────────────────────┼───────────────────────────────────┤
│ docker-compose.yml          │ docker-compose.demo.yml           │
│ .env.dev                    │ .env.demo                         │
│ target: development         │ target: production                │
│ 源碼掛載 (hot reload)       │ 代碼打包進 image (穩定)           │
│ Ports: 180xx                │ Ports: 181xx                      │
│ Containers: form_analysis_* │ Containers: demo_form_analysis_*  │
│ Volumes: postgres_data      │ Volumes: postgres_demo_data       │
└─────────────────────────────┴───────────────────────────────────┘
```

**核心原則**：
- 開發時修改代碼 → 僅影響開發環境（即時生效）
- Demo 環境使用固定 images → 需明確執行 build 才會更新
- 兩環境可同時運行，互不影響

---

## 環境差異對照

| 項目 | 開發環境 | Demo 環境 |
|------|----------|-----------|
| Compose 檔案 | `docker-compose.yml` | `docker-compose.demo.yml` |
| 環境變數檔 | `.env.dev` | `.env.demo` |
| Build Target | `development` | `production` |
| 源碼掛載 | ✅ 是（hot reload） | ❌ 否（打包進 image） |
| PostgreSQL Port | 18001 | 18101 |
| Backend API Port | 18002 | 18102 |
| Frontend Port | 18003 | 18103 |
| pgAdmin Port | 18004 | 18104 |
| Container 前綴 | `form_analysis_` | `demo_form_analysis_` |
| Volume 前綴 | `postgres_data` | `postgres_demo_data` |
| DEBUG 模式 | true | false |
| RELOAD 模式 | true | false |

---

## 操作步驟

### 開發環境啟動

```batch
cd scripts
start-dev.bat
```

**執行流程**：
1. 讀取 `.env.dev` 設定
2. 停止現有開發容器
3. 使用 `docker-compose.yml` 啟動（development target）
4. 源碼自動掛載，修改即時生效

**存取位置**：
- Frontend: http://localhost:18003
- Backend API: http://localhost:18002
- API Docs: http://localhost:18002/docs
- PostgreSQL: localhost:18001

### Demo 環境建置與啟動

#### 首次使用或代碼更新後

```batch
cd scripts

:: 1. 建立 Demo images（含目前代碼）
build-demo-images.bat

:: 2. 啟動 Demo 環境
start-demo.bat
```

#### 之後啟動（使用既有 images）

```batch
cd scripts
start-demo.bat
```

**存取位置**：
- Frontend: http://localhost:18103
- Backend API: http://localhost:18102
- API Docs: http://localhost:18102/docs
- PostgreSQL: localhost:18101
- ngrok: ngrok http 18103
### 併行執行

兩環境可同時執行：

```batch
:: Terminal 1 - 啟動開發環境
cd scripts
start-dev.bat

:: Terminal 2 - 啟動 Demo 環境
cd scripts
start-demo.bat
```

**驗證併行狀態**：
```batch
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

應看到類似：
```
NAMES                        STATUS          PORTS
form_analysis_frontend       Up 2 minutes    0.0.0.0:18003->5173/tcp
form_analysis_api            Up 2 minutes    0.0.0.0:18002->8000/tcp
form_analysis_db             Up 2 minutes    0.0.0.0:18001->5432/tcp
demo_form_analysis_frontend  Up 5 minutes    0.0.0.0:18103->80/tcp
demo_form_analysis_api       Up 5 minutes    0.0.0.0:18102->8000/tcp
demo_form_analysis_db        Up 5 minutes    0.0.0.0:18101->5432/tcp
```

---

## 故障排除

### 問題 1：Port 衝突

**症狀**：
```
Error: Bind for 0.0.0.0:18102 failed: port is already allocated
```

**解決方案**：
```batch
:: 檢查佔用該 port 的程序
netstat -ano | findstr :18102

:: 停止佔用的容器
docker stop <container_name>

:: 或停止整個環境
cd form-analysis-server
docker-compose -f docker-compose.demo.yml down
```

### 問題 2：Demo images 不存在

**症狀**：
```
Error: No such image: form-analysis-backend:demo
```

**原因**：首次啟動 Demo 前未建立 images

**解決方案**：
```batch
cd scripts
build-demo-images.bat
start-demo.bat
```

### 問題 3：Backend healthcheck 失敗

**症狀**：
```
Container demo_form_analysis_api is unhealthy
```

**排查步驟**：
```batch
:: 查看容器日誌
docker logs demo_form_analysis_api --tail=100

:: 常見原因：
:: - 資料庫連線失敗 → 檢查 db 容器是否正常
:: - 環境變數錯誤 → 檢查 .env.demo 設定
```

**解決方案**：
```batch
:: 重新啟動 db
docker restart demo_form_analysis_db

:: 等待約 30 秒後重啟 backend
docker restart demo_form_analysis_api
```

### 問題 4：Frontend 無法連接 Backend

**症狀**：
- 頁面顯示但 API 呼叫失敗
- Network Error 或 CORS 錯誤

**排查步驟**：
```batch
:: 確認 backend 正在運行
curl http://localhost:18102/healthz

:: 檢查 CORS 設定
docker exec demo_form_analysis_api printenv CORS_ORIGINS
```

**解決方案**：
1. 確認 `.env.demo` 中 `CORS_ORIGINS` 包含 frontend URL
2. 確認 `VITE_API_URL` 設定正確

### 問題 5：資料庫連線錯誤

**症狀**：
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**排查步驟**：
```batch
:: 檢查 db 容器狀態
docker ps | findstr demo_form_analysis_db

:: 查看 db 日誌
docker logs demo_form_analysis_db --tail=50
```

**解決方案**：
```batch
:: 重啟 db 容器
docker restart demo_form_analysis_db

:: 若持續失敗，移除 volume 重建（注意：會清除資料）
docker volume rm form-analysis-server_postgres_demo_data
start-demo.bat
```

### 問題 6：開發環境 hot reload 不生效

**症狀**：修改代碼後 frontend/backend 沒有自動重載

**原因**：可能使用了錯誤的 compose 檔案

**解決方案**：
1. 確認使用 `docker-compose.yml`（非 demo.yml）
2. 確認 build target 是 `development`
3. 檢查源碼 volume 掛載：
   ```batch
   docker inspect form_analysis_api | findstr Mounts -A 10
   ```

### 問題 7：磁碟空間不足

**症狀**：
```
No space left on device
```

**解決方案**：
```batch
:: 清理未使用的 Docker 資源
docker system prune -a

:: 清理未使用的 volumes
docker volume prune
```

---

## 常見問題 FAQ

### Q1: 什麼時候需要執行 build-demo-images.bat？

**A**: 以下情況需要重新建立 Demo images：
- 首次部署 Demo 環境
- Backend 或 Frontend 代碼有更新需要發布到 Demo
- Dockerfile 有修改
- 依賴套件有更新（requirements.txt / package.json）

### Q2: 開發環境和 Demo 環境的資料庫是獨立的嗎？

**A**: 是的。兩環境使用獨立的 volumes：
- 開發：`postgres_data`
- Demo：`postgres_demo_data`

資料完全隔離，互不影響。

### Q3: 如何將開發環境的資料匯出到 Demo？

**A**: 
```batch
:: 匯出開發環境資料
docker exec form_analysis_db pg_dump -U app form_analysis_dev_db > backup.sql

:: 匯入到 Demo 環境
docker exec -i demo_form_analysis_db psql -U app form_analysis_demo_db < backup.sql
```

### Q4: 可以只啟動單一服務嗎？

**A**: 可以。
```batch
cd form-analysis-server

:: 只啟動 backend
docker-compose -f docker-compose.demo.yml --env-file .env.demo up -d backend

:: 只啟動 frontend
docker-compose -f docker-compose.demo.yml --env-file .env.demo up -d frontend
```

### Q5: 如何查看特定容器的日誌？

**A**:
```batch
:: 即時查看日誌
docker logs -f demo_form_analysis_api

:: 查看最近 100 行
docker logs demo_form_analysis_api --tail=100
```

### Q6: Demo 環境如何完全重置？

**A**:
```batch
cd form-analysis-server

:: 停止並移除所有 Demo 容器和 volumes
docker-compose -f docker-compose.demo.yml down -v

:: 移除 images（可選）
docker rmi form-analysis-backend:demo form-analysis-frontend:demo

:: 重新建立
cd ../scripts
build-demo-images.bat
start-demo.bat
```

---

## 相關文件

- [DUAL_ENV_STARTUP_CHECKLIST.md](DUAL_ENV_STARTUP_CHECKLIST.md) - 雙環境啟動檢查清單
- [STARTUP_SCRIPT_FEATURES.md](STARTUP_SCRIPT_FEATURES.md) - 啟動腳本功能說明
- [TENANT_INIT_ADMIN_GUIDE.md](TENANT_INIT_ADMIN_GUIDE.md) - 租戶初始化指南
