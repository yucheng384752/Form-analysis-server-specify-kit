# 啟動腳本功能說明

## 概述
`start-system.bat` 是表單分析系統的自動化啟動腳本，提供完整的系統初始化和啟動功能。

## 主要功能

### 1. ✅ 自動清理佔用端口

腳本會自動檢測並清理以下端口的衝突：

| 端口 | 用途 | 處理方式 |
|------|------|----------|
| 5432 | PostgreSQL 資料庫 | 自動停止佔用該端口的 Docker 容器 |
| 8000 | Backend API | 自動停止佔用該端口的 Docker 容器 |
| 3000 | 備用前端端口 | 自動停止佔用該端口的 Docker 容器 |
| 5173 | Vite 前端開發服務器 | 自動停止佔用該端口的 Docker 容器 |

**工作原理：**
```batch
1. 使用 netstat 檢測端口是否被監聽
2. 使用 docker ps 查找佔用端口的容器
3. 自動執行 docker stop 停止衝突容器
4. 清理殘留的 Docker 網路和資源
```

### 2. ✅ 首次啟動自動初始化資料庫

腳本能夠智能識別是否為首次啟動，並執行相應的初始化流程。

#### 首次啟動檢測
- 檢查 Docker volume `form-analysis-server_postgres_data` 是否存在
- 若不存在，判定為首次啟動

#### 初始化流程

**資料庫層（PostgreSQL）：**
1. 執行 `init.sql` 創建基礎表結構
   - 創建 UUID 擴展
   - 創建 forms 表
   - 創建 analysis_results 表
   - 創建必要的索引

**應用層（Backend）：**
1. 通過 `entrypoint.sh` 自動執行
2. 等待資料庫就緒（pg_isready 檢查）
3. 執行 Alembic 資料庫遷移
   - 自動升級到最新版本 (`alembic upgrade head`)
   - 應用 P1/P2/P3 資料類型支援
   - 創建所有必要的表和欄位
4. 創建 uploads 目錄並設置權限

#### 狀態監控
```batch
✅ 資料庫已就緒（健康檢查通過）
   🔧 首次啟動：檢查資料庫初始化...
   ✅ 資料庫初始化腳本執行成功

✅ 後端服務已就緒（健康檢查通過）
   🔍 檢查資料庫遷移執行狀態...
   ✅ 資料庫遷移執行成功
```

### 3. ✅ 健康檢查與容錯機制

#### 資料庫健康檢查
- 最多等待 120 秒（60 次檢查，每次 2 秒）
- 檢查容器運行狀態
- 檢查 PostgreSQL 健康狀態
- 失敗時顯示詳細診斷資訊

#### 後端服務健康檢查
- 最多等待 90 秒（45 次檢查，每次 2 秒）
- 檢查容器運行狀態
- 檢查 HTTP 健康端點
- 驗證資料庫遷移執行狀態

#### 前端服務健康檢查
- 最多等待 80 秒（40 次檢查，每次 2 秒）
- 檢查 Vite 開發服務器狀態
- 驗證前端可訪問性

### 4. 自動化監控終端

啟動完成後自動開啟兩個監控終端：
- **後端監控** - 顯示 API 和資料庫日誌
- **前端監控** - 顯示前端應用日誌

## 使用方式

### 標準啟動
```batch
cd c:\Users\Yucheng\Desktop\form-analysis-sepc-kit\scripts
start-system.bat
```

### 首次啟動
第一次執行時，腳本會：
1. 檢測到無現有資料卷
2. 顯示 "🆕 檢測到首次啟動，將執行完整初始化"
3. 自動執行所有初始化步驟
4. 創建資料庫結構並應用遷移

### 後續啟動
之後的啟動會：
1. 檢測到現有資料卷
2. 顯示 "🔄 檢測到現有資料，將執行正常啟動"
3. 保留現有資料，正常啟動服務

## 技術細節

### 資料庫遷移檔案位置
```
form-analysis-server/backend/alembic/versions/
├── 2025_11_08_0122-ae889647f4f2_create_initial_tables_upload_jobs_.py
└── 2025_11_10_0110-d0c4b28c0776_add_p1_p2_p3_data_types.py
```

### Entrypoint 腳本
位置: `form-analysis-server/backend/entrypoint.sh`

主要功能：
- 等待資料庫就緒
- 執行 Alembic 遷移
- 創建必要目錄
- 啟動應用服務器

### Docker Compose 配置
- 資料庫使用持久化卷 `postgres_data`
- 自動掛載 `init.sql` 到初始化目錄
- Backend 使用 entrypoint 腳本
- 所有服務配置健康檢查

## 常見問題排除

### 端口被佔用
**問題**: 提示端口已被使用
**解決**: 腳本會自動停止衝突的 Docker 容器

### 資料庫啟動失敗
**檢查項目**:
1. Docker Desktop 是否運行
2. 是否有足夠的系統資源
3. 查看資料庫日誌: `docker-compose logs db`

### 遷移執行失敗
**檢查項目**:
1. 資料庫連線是否正常
2. Alembic 配置是否正確
3. 查看後端日誌: `docker-compose logs backend`

### 完全重置
如需完全重置系統（清除所有資料）：
```batch
cd form-analysis-server
docker-compose down -v
```
下次啟動將視為首次啟動並重新初始化。

## 服務訪問

啟動成功後可訪問：
- 🌐 前端應用: http://localhost:5173
- 📚 API 文檔: http://localhost:8000/docs
- 🔧 API 測試: http://localhost:8000/redoc
- 🏥 健康檢查: http://localhost:8000/healthz

## 停止服務

```batch
cd form-analysis-server
docker-compose down
```

保留資料，僅停止容器。

## 更新日誌

### 2025-11-15
- ✅ 新增所有端口的自動衝突檢測和清理
- ✅ 實作首次啟動智能檢測
- ✅ 新增 Alembic 資料庫遷移自動執行
- ✅ 新增 entrypoint.sh 腳本
- ✅ 改進健康檢查和錯誤處理
- ✅ 新增初始化狀態監控和日誌
