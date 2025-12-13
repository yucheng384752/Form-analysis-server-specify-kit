# Form Analysis API - 一鍵啟動與驗證指令摘要

##  一鍵啟動命令

### Docker Compose 啟動
```bash
# 啟動所有服務
docker compose up -d

# 檢查服務狀態
docker compose ps

# 查看日誌
docker compose logs -f
```

### 使用自動化腳本

**Windows (PowerShell)**
```powershell
# 完整啟動和測試
.\quick-start.ps1

# 只啟動服務，跳過測試
.\quick-start.ps1 -SkipTests
```

**Linux/macOS**
```bash
chmod +x quick-start.sh
./quick-start.sh
```

## 🩺 健康檢查驗證

### 基本健康檢查
```bash
curl -f http://localhost:8000/healthz
```

**預期回應：**
```json
{
  "status": "healthy",
  "timestamp": "2024-11-08T10:30:00Z",
  "version": "1.0.0"
}
```

### 詳細健康檢查
```bash
curl -f http://localhost:8000/healthz/detailed
```

**預期回應：**
```json
{
  "status": "healthy",
  "timestamp": "2024-11-08T10:30:00Z",
  "version": "1.0.0",
  "database": {
    "status": "connected",
    "response_time_ms": 15
  },
  "uptime_seconds": 3600
}
```

##  檔案上傳與驗證流程

### 1. 創建測試 CSV 檔案

**5 列範例資料：**
```bash
cat << 'EOF' > test_upload.csv
lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
2345678_02,測試產品B,50,2024-01-16
3456789_03,測試產品C,75,2024-01-17
4567890_04,測試產品D,200,2024-01-18
5678901_05,測試產品E,125,2024-01-19
EOF
```

### 2. 上傳檔案
```bash
curl -X POST \
     -F "file=@test_upload.csv" \
     http://localhost:8000/api/upload
```

**成功回應範例：**
```json
{
  "success": true,
  "message": "檔案上傳成功",
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "test_upload.csv",
  "total_rows": 5,
  "has_errors": false
}
```

### 3. 內聯 CSV 上傳 (使用 --form file=@-)
```bash
curl -X POST \
     -H "Content-Type: multipart/form-data" \
     --form 'file=@-;filename=inline.csv;type=text/csv' \
     http://localhost:8000/api/upload << 'EOF'
lot_no,product_name,quantity,production_date
7777777_01,內聯產品A,10,2024-02-01
8888888_02,內聯產品B,20,2024-02-02
9999999_03,內聯產品C,30,2024-02-03
1111111_04,內聯產品D,40,2024-02-04
2222222_05,內聯產品E,50,2024-02-05
EOF
```

### 4. 下載錯誤報告（如果有錯誤）
```bash
# 使用上傳回應中的 file_id
curl "http://localhost:8000/api/errors.csv?file_id=550e8400-e29b-41d4-a716-446655440000"
```

**錯誤報告 CSV 格式：**
```csv
row,column,value,error
2,lot_no,123456,"格式錯誤：應為 7digits_2digits 格式"
3,product_name,"","產品名稱不能為空"
4,quantity,-10,"數量不能為負數"
5,production_date,2024-13-45,"日期格式錯誤：應為 YYYY-MM-DD"
```

### 5. 確認資料匯入
```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"file_id":"550e8400-e29b-41d4-a716-446655440000"}' \
     http://localhost:8000/api/import
```

**成功匯入回應：**
```json
{
  "success": true,
  "message": "資料匯入完成",
  "imported_rows": 5,
  "failed_rows": 0
}
```

## 🧪 完整測試流程腳本

### 使用自動測試腳本

**PowerShell**
```powershell
.\test-api.ps1
```

**Bash**
```bash
chmod +x test-api.sh
./test-api.sh
```

### 手動測試步驟

```bash
# 1. 健康檢查
curl -f http://localhost:8000/healthz

# 2. 上傳測試檔案
FILE_ID=$(curl -s -X POST -F "file=@test_upload.csv" http://localhost:8000/api/upload | \
          grep -o '"file_id":"[^"]*"' | cut -d'"' -f4)

echo "File ID: $FILE_ID"

# 3. 檢查錯誤（如果有）
curl "http://localhost:8000/api/errors.csv?file_id=$FILE_ID"

# 4. 匯入資料
curl -X POST \
     -H "Content-Type: application/json" \
     -d "{\"file_id\":\"$FILE_ID\"}" \
     http://localhost:8000/api/import

# 5. 清理
rm test_upload.csv
```

##  前端訪問

### URL 和埠口
- **前端應用**: http://localhost:5173
- **後端 API**: http://localhost:8000
- **API 文件**: http://localhost:8000/docs
- **ReDoc 文件**: http://localhost:8000/redoc

### 前端環境配置

**在 `.env` 文件中配置：**
```env
# API 基礎 URL
VITE_API_URL=http://localhost:8000

# 最大檔案大小 (位元組)
VITE_MAX_FILE_SIZE=10485760

# CORS 來源
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**在 `vite.config.ts` 中的代理設定：**
```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
```

##  CORS 配置確認

### 後端 CORS 設定
在 `.env` 文件中配置允許的來源：
```env
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
```

### 測試 CORS
```bash
# 測試 OPTIONS 預檢請求
curl -X OPTIONS \
     -H "Origin: http://localhost:5173" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     http://localhost:8000/api/upload
```

##  常用除錯指令

### 檢查容器狀態
```bash
docker compose ps
docker compose logs backend
docker compose logs frontend  
docker compose logs db
```

### 重啟服務
```bash
# 重啟所有服務
docker compose restart

# 重啟特定服務
docker compose restart backend

# 重建並啟動
docker compose down
docker compose up -d --build
```

### 清理和重置
```bash
# 停止並刪除容器
docker compose down

# 停止並刪除容器與資料卷
docker compose down -v

# 完全清理（包括映像）
docker compose down -v --rmi all
```

##  快速驗證檢查表

- [ ] 所有容器正常啟動: `docker compose ps`
- [ ] 基本健康檢查通過: `curl -f http://localhost:8000/healthz`
- [ ] 詳細健康檢查通過: `curl -f http://localhost:8000/healthz/detailed`
- [ ] 檔案上傳功能正常: 使用測試 CSV
- [ ] 錯誤報告下載正常: 如果有驗證錯誤
- [ ] 資料匯入功能正常: 確認匯入 API
- [ ] 前端可正常訪問: http://localhost:5173
- [ ] API 文件可訪問: http://localhost:8000/docs

## 🆘 常見問題快速修復

### 埠口衝突
```bash
# 檢查埠口使用情況
netstat -ano | findstr :8000    # Windows
lsof -i :8000                   # Linux/macOS

# 修改 .env 中的埠口設定
API_PORT=8001
FRONTEND_PORT=3000
```

### Docker 權限問題
```bash
# 確保 Docker 正在運行
docker info

# 重啟 Docker Desktop（Windows）
# 或重啟 Docker 服務（Linux）
```

### 前端 CORS 問題
```bash
# 檢查 .env 中的 CORS_ORIGINS 設定
# 確保包含前端 URL
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

這個摘要提供了完整的一鍵啟動與驗證流程，可以快速驗證整個系統的功能！