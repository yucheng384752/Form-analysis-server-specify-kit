# 資料庫清空問題修復報告

## 問題描述

使用 `start-system.bat` 啟動腳本時,資料庫內容被意外清空。

##  根本原因分析

### 問題程式碼位置
**檔案**: `scripts/start-system.bat`  
**行號**: 103

```bat
if "!port_conflict!"=="true" (
    echo     執行額外清理以釋放端口...
    docker-compose -f "%SERVER_PATH%\docker-compose.yml" down -v --remove-orphans >nul 2>&1
    timeout /t 2 /nobreak >nul
)
```

### 問題詳解

當檢測到端口衝突時(5432, 8000, 3000, 5173),腳本會執行 `docker-compose down -v`。

**`-v` 參數的影響**:
```bash
docker-compose down -v
```
- `-v` = `--volumes`
- **會刪除所有 Docker Volume**
- **包括 `postgres_data` 資料卷**
- **導致所有資料庫資料永久丟失** 

### 觸發條件

當以下任一端口被佔用時會觸發:
1. **5432** - PostgreSQL 資料庫
2. **8000** - 後端 API
3. **3000** - 備用前端端口
4. **5173** - Vite 開發伺服器

腳本偵測流程:
```bat
netstat -an | find ":5432" | find "LISTENING"
↓ 發現端口被佔用
port_conflict=true
↓ 執行清理
docker-compose down -v  ← 這裡會刪除資料!
```

##  修復方案

### 修改內容

**修改前**:
```bat
docker-compose -f "%SERVER_PATH%\docker-compose.yml" down -v --remove-orphans
```

**修改後**:
```bat
docker-compose -f "%SERVER_PATH%\docker-compose.yml" down --remove-orphans
```

### 修復說明

移除 `-v` 參數:
-  **保留** Docker Volume (資料庫資料)
-  **停止並移除**容器
-  **清理**孤立容器
-  **釋放**被佔用的端口

## 資料安全機制

### Docker Volume 生命週期

| 操作 | Volume 保留 | 資料安全 |
|------|------------|---------|
| `docker-compose down` |  保留 |  安全 |
| `docker-compose down --remove-orphans` |  保留 |  安全 |
| `docker-compose down -v` |  **刪除** |  **資料丟失** |
| `docker-compose stop` |  保留 |  安全 |
| `docker-compose restart` |  保留 |  安全 |

### Volume 資料位置

```yaml
# docker-compose.yml
volumes:
  postgres_data:  # ← 資料庫資料儲存位置
    driver: local
```

資料實際儲存在:
- **Windows**: `C:\ProgramData\Docker\volumes\form-analysis-server_postgres_data\_data`
- **Linux/Mac**: `/var/lib/docker/volumes/form-analysis-server_postgres_data/_data`

##  手動資料管理

### 查看現有 Volume

```bash
docker volume ls | findstr postgres
```

### 備份資料庫

```bash
# 備份到檔案
docker exec form_analysis_db pg_dump -U app form_analysis_db > backup.sql

# 使用 Docker Volume 備份
docker run --rm -v form-analysis-server_postgres_data:/data -v %cd%:/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

### 還原資料庫

```bash
# 從 SQL 檔案還原
docker exec -i form_analysis_db psql -U app -d form_analysis_db < backup.sql

# 從 Volume 備份還原
docker run --rm -v form-analysis-server_postgres_data:/data -v %cd%:/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /data
```

### 僅在需要時刪除資料

如果**確實需要清空資料庫**,使用明確的命令:

```bash
#  警告:這會刪除所有資料!
cd form-analysis-server
docker-compose down -v

# 或手動刪除 Volume
docker volume rm form-analysis-server_postgres_data
```

##  影響評估

### 修復前的風險

- **高風險**: 任何端口衝突都會導致資料丟失
- **無警告**: 用戶不知道資料會被刪除
- **不可恢復**: Volume 刪除後資料無法還原

### 修復後的改善

-  **資料持久化**: Volume 始終保留
-  **安全清理**: 只清理容器,不影響資料
-  **端口管理**: 正確停止衝突容器

## 測試驗證

### 測試步驟

1. **插入測試資料**:
```bash
docker exec -i form_analysis_db psql -U app -d form_analysis_db -c "SELECT COUNT(*) FROM records;"
```

2. **模擬端口衝突**:
```bash
# 啟動一個佔用 5432 的容器
docker run -d -p 5432:5432 --name test_postgres postgres:16
```

3. **執行啟動腳本**:
```bash
cd scripts
.\start-system.bat
```

4. **驗證資料保留**:
```bash
docker exec form_analysis_db psql -U app -d form_analysis_db -c "SELECT COUNT(*) FROM records;"
```

### 預期結果

-  偵測到端口衝突
-  自動停止衝突容器
-  系統正常啟動
-  **資料完整保留**

##  相關文件更新

### 需要同步更新的文件

1. **啟動指南**: 
   - `docs/MANUAL_STARTUP_GUIDE.md` - 說明資料不會被清空

2. **部署指南**:
   - `DEPLOYMENT_GUIDE.md` - 更新資料安全說明

3. **系統需求**:
   - `SYSTEM_REQUIREMENTS.md` - 補充 Volume 管理說明

##  最佳實踐建議

### 開發環境

1. **定期備份**: 
```bash
# 建議每日備份
docker exec form_analysis_db pg_dump -U app form_analysis_db > backup_$(date +%Y%m%d).sql
```

2. **測試前備份**:
```bash
# 重大修改前先備份
docker run --rm -v form-analysis-server_postgres_data:/data -v %cd%:/backup alpine tar czf /backup/pre_test_backup.tar.gz -C /data .
```

### 生產環境

1. **使用外部資料庫**: 不要依賴 Docker Volume
2. **自動化備份**: 設定 cron job 定期備份
3. **監控告警**: 設定資料庫監控和備份驗證

##  相關參考

- Docker Compose Down 文件: https://docs.docker.com/engine/reference/commandline/compose_down/
- Docker Volume 管理: https://docs.docker.com/storage/volumes/
- PostgreSQL 備份還原: https://www.postgresql.org/docs/current/backup-dump.html

---

**修復時間**: 2025-11-15  
**影響範圍**: `scripts/start-system.bat`  
**修復狀態**:  已完成  
**測試狀態**:  待驗證
