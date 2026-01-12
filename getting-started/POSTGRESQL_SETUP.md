# PostgreSQL 配置說明

##  資料庫要求

**系統固定使用 PostgreSQL 資料庫，不支援其他資料庫類型。**

##  快速啟動

### 方法1: 使用Docker (推薦)

1. **啟動PostgreSQL服務**
```bash
# Windows
.\setup-postgresql.bat

# PowerShell  
.\setup-postgresql.ps1

# 或手動啟動
docker-compose up -d db
```

2. **初始化資料庫**
```bash
cd backend
python setup_postgresql.py
```

3. **啟動應用程式**
```bash
# 後端
cd backend
python app/main.py

# 前端 (新終端)
cd frontend  
npm run dev
```

### 方法2: 本地PostgreSQL

1. **安裝PostgreSQL 16+**
2. **創建資料庫**
```sql
CREATE DATABASE form_analysis_db;
CREATE USER app WITH PASSWORD 'app_secure_password_2024';
GRANT ALL PRIVILEGES ON DATABASE form_analysis_db TO app;
```

3. **配置連接**
```env
DATABASE_URL=postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db
```

##  配置檔案

### `.env` 設定
```properties
# PostgreSQL 資料庫 (必須)
DATABASE_URL=postgresql+asyncpg://app:app_secure_password_2024@localhost:18001/form_analysis_db

# API 設定
API_HOST=0.0.0.0
API_PORT=8000

# 其他設定...
```

## 安全提醒

-  只支援 PostgreSQL
-  使用連接池
-  異步操作
-  自動重連
-  不支援 SQLite
-  不支援 MySQL

##  資料庫管理

### 使用pgAdmin (可選)
```bash
docker-compose up -d pgadmin --profile tools
```
訪問: http://localhost:5050
- 郵箱: admin@example.com  
- 密碼: admin

### 手動操作
```bash
# 查看日誌
docker-compose logs db

# 進入容器
docker-compose exec db psql -U app -d form_analysis_db

# 停止服務
docker-compose down
```

##  故障排除

### 常見問題

1. **連接失敗**
```
解決: 確認PostgreSQL服務正在運行
docker-compose ps db
```

2. **權限錯誤** 
```
解決: 檢查用戶權限和密碼
```

3. **端口衝突**
```
解決: 修改 docker-compose.yml 中的端口映射
```

##  相關指令

```bash
# 檢查容器狀態
docker-compose ps

# 查看資料庫日誌  
docker-compose logs -f db

# 重啟資料庫
docker-compose restart db

# 清理並重建
docker-compose down -v
docker-compose up -d db
```