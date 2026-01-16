#!/bin/bash

# Form Analysis - Docker 一鍵啟動與驗證腳本
# 
# 此腳本將：
# 1. 啟動所有服務
# 2. 等待服務就緒
# 3. 驗證健康檢查
# 4. 模擬完整的上傳和驗證流程
# 5. 提供前端訪問資訊

set -e  # 遇到錯誤立即退出

# Optional flag: --reset-db will remove Docker volumes (DANGEROUS: clears DB data)
RESET_DB=false
if [ "${1:-}" = "--reset-db" ]; then
    RESET_DB=true
fi

echo " Form Analysis - Docker 一鍵啟動與驗證"
echo "========================================"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函數：彩色輸出
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查 Docker 是否運行
if ! docker info >/dev/null 2>&1; then
    print_error "Docker 未運行，請先啟動 Docker"
    exit 1
fi

# 檢查 curl 是否可用
if ! command -v curl &> /dev/null; then
    print_error "curl 未安裝，請先安裝 curl"
    exit 1
fi

print_status "停止現有容器..."
if [ "$RESET_DB" = "true" ]; then
    print_warning "--reset-db：將移除 Docker volumes，資料庫資料會被清空"
    docker compose down -v --remove-orphans
else
    # Default: keep volumes to preserve DB data
    docker compose down --remove-orphans
fi

print_status "啟動所有服務..."
docker compose up -d

print_status "等待服務啟動..."
sleep 10

# 等待資料庫就緒
print_status "等待資料庫就緒..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose exec -T db pg_isready -U app >/dev/null 2>&1; then
        print_success "資料庫已就緒"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "資料庫啟動超時"
    docker compose logs db
    exit 1
fi

# 等待後端 API 就緒
print_status "等待後端 API 就緒..."
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:18002/healthz >/dev/null 2>&1; then
        print_success "後端 API 已就緒"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "後端 API 啟動超時"
    docker compose logs backend
    exit 1
fi

# 等待前端就緒
print_status "等待前端就緒..."
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:18003 >/dev/null 2>&1; then
        print_success "前端已就緒"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "前端啟動超時"
    docker compose logs frontend
    exit 1
fi

echo ""
print_success "所有服務已啟動完成！"
echo ""

# If Docker defaults to AUTH_MODE=api_key, bootstrap a tenant API key for smoke tests.
API_KEY=""
AUTH_HEADER=()
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:18002/api/tenants || true)
if [ "$HTTP_CODE" = "401" ]; then
    print_status "偵測到 API key auth 已啟用，bootstrap 測試用 API key..."
    BOOTSTRAP_OUT=$(docker compose exec -T backend python scripts/bootstrap_tenant_api_key.py --tenant-code default --label docker-quick-start --force)
    API_KEY=$(echo "$BOOTSTRAP_OUT" | awk '/SAVE THIS KEY NOW/{getline; print; exit}' | tr -d '\r' | xargs)
    if [ -z "$API_KEY" ]; then
        # fallback: last non-empty line
        API_KEY=$(echo "$BOOTSTRAP_OUT" | awk 'NF{line=$0} END{print line}' | tr -d '\r' | xargs)
    fi
    if [ -z "$API_KEY" ]; then
        print_error "bootstrap API key 失敗：無法解析輸出"
        exit 1
    fi
    print_success "已建立/取得測試用 API key（請在註冊頁貼上）：$API_KEY"
    AUTH_HEADER=(-H "X-API-Key: $API_KEY")
fi

# 驗證健康檢查
echo "🩺 健康檢查驗證"
echo "=================="

print_status "測試基本健康檢查..."
if curl -f http://localhost:18002/healthz; then
    print_success "基本健康檢查通過"
else
    print_error "基本健康檢查失敗"
    exit 1
fi

echo ""
print_status "測試詳細健康檢查..."
if curl -f http://localhost:18002/healthz/detailed; then
    print_success "詳細健康檢查通過"
else
    print_warning "詳細健康檢查失敗（可能尚未實現）"
fi

echo ""

# 模擬上傳與驗證流程
echo " 模擬上傳與驗證流程"
echo "======================="

# 創建測試 CSV 文件
TEST_CSV_CONTENT="lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
2345678_02,測試產品B,50,2024-01-16
3456789_03,測試產品C,75,2024-01-17
4567890_04,測試產品D,200,2024-01-18
5678901_05,測試產品E,125,2024-01-19"

# 創建臨時文件
TEMP_CSV=$(mktemp --suffix=.csv)
echo "$TEST_CSV_CONTENT" > "$TEMP_CSV"

print_status "測試檔案上傳（5 列測試資料）..."

UPLOAD_RESPONSE=$(curl -s -X POST \
    "${AUTH_HEADER[@]}" \
    -F "file=@$TEMP_CSV" \
    http://localhost:18002/api/upload)

echo "上傳回應: $UPLOAD_RESPONSE"

# 解析 file_id（簡單的 JSON 解析）
FILE_ID=$(echo "$UPLOAD_RESPONSE" | grep -o '"file_id":"[^"]*"' | cut -d'"' -f4)

if [ -n "$FILE_ID" ]; then
    print_success "檔案上傳成功，file_id: $FILE_ID"
    
    # 測試錯誤報告下載
    print_status "測試錯誤報告下載..."
    if curl -f "${AUTH_HEADER[@]}" "http://localhost:18002/api/errors.csv?file_id=$FILE_ID" -o /tmp/errors.csv; then
        print_success "錯誤報告下載成功"
        echo "錯誤報告內容："
        cat /tmp/errors.csv
        echo ""
    else
        print_warning "錯誤報告下載失敗或無錯誤"
    fi
    
    # 測試資料匯入
    print_status "測試資料匯入..."
    IMPORT_RESPONSE=$(curl -s -X POST \
        "${AUTH_HEADER[@]}" \
        -H "Content-Type: application/json" \
        -d "{\"file_id\":\"$FILE_ID\"}" \
        http://localhost:18002/api/import)
    
    echo "匯入回應: $IMPORT_RESPONSE"
    print_success "資料匯入測試完成"
else
    print_error "檔案上傳失敗"
fi

# 清理臨時文件
rm -f "$TEMP_CSV"

echo ""
echo " 前端訪問資訊"
echo "================"
print_success "前端應用已啟動: http://localhost:18003"
print_success "後端 API 文件: http://localhost:18002/docs"
print_success "後端 API Redoc: http://localhost:18002/redoc"

echo ""
echo " 環境配置說明"
echo "================"
echo "• API Base URL: 在 .env 文件中配置 VITE_API_URL"
echo "• 檔案大小限制: 在 .env 文件中配置 VITE_MAX_FILE_SIZE"
echo "• CORS 設定: 在 .env 文件中配置 CORS_ORIGINS"
echo ""
echo " vite.config.ts 代理設定已配置 /api 路徑到後端"
echo ""

echo " 容器狀態"
echo "==========="
docker compose ps

echo ""
print_success " 一鍵啟動與驗證完成！"
echo ""
echo "使用以下命令查看日誌："
echo "  docker compose logs -f backend    # 後端日誌"
echo "  docker compose logs -f frontend   # 前端日誌"
echo "  docker compose logs -f db         # 資料庫日誌"
echo ""
echo "停止服務："
echo "  docker compose down"
echo ""
echo "停止並清理資料："
echo "  docker compose down -v"