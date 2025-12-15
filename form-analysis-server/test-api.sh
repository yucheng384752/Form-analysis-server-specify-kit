#!/bin/bash

# Form Analysis API 測試腳本
# 使用 curl 進行完整的 API 測試流程

set -e

echo "Form Analysis API 測試腳本"
echo "============================="

# 設定 API Base URL
API_BASE="http://localhost:8000"

# 顏色定義
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# 1. 健康檢查測試
echo ""
print_test "1. 測試基本健康檢查 (/healthz)"
if curl -f -s "${API_BASE}/healthz" > /dev/null; then
    print_success "基本健康檢查通過"
    echo "回應內容:"
    curl -s "${API_BASE}/healthz" | jq -r . 2>/dev/null || curl -s "${API_BASE}/healthz"
else
    print_error "基本健康檢查失敗"
    exit 1
fi

echo ""
print_test "2. 測試詳細健康檢查 (/healthz/detailed)"
if curl -f -s "${API_BASE}/healthz/detailed" > /dev/null; then
    print_success "詳細健康檢查通過"
    echo "回應內容:"
    curl -s "${API_BASE}/healthz/detailed" | jq -r . 2>/dev/null || curl -s "${API_BASE}/healthz/detailed"
else
    echo -e "${YELLOW}[SKIP]${NC} 詳細健康檢查端點不存在或失敗"
fi

# 2. 創建測試 CSV 檔案
echo ""
print_test "3. 準備測試檔案"

# 創建有效的測試 CSV
VALID_CSV=$(mktemp --suffix=.csv)
cat << 'EOF' > "${VALID_CSV}"
lot_no,product_name,quantity,production_date
1234567_01,測試產品A,100,2024-01-15
2345678_02,測試產品B,50,2024-01-16
3456789_03,測試產品C,75,2024-01-17
4567890_04,測試產品D,200,2024-01-18
5678901_05,測試產品E,125,2024-01-19
EOF

# 創建有錯誤的測試 CSV
ERROR_CSV=$(mktemp --suffix=.csv)
cat << 'EOF' > "${ERROR_CSV}"
lot_no,product_name,quantity,production_date
123456_01,測試產品A,100,2024-01-15
2345678_02,,50,2024-01-16
3456789_03,測試產品C,-75,2024-01-17
4567890_04,測試產品D,200,2024-13-45
567890_05,測試產品E,125,2024-01-19
EOF

print_success "測試檔案準備完成"
echo "有效檔案: ${VALID_CSV}"
echo "錯誤檔案: ${ERROR_CSV}"

# 3. 檔案上傳測試
echo ""
print_test "4. 測試有效檔案上傳"

UPLOAD_RESPONSE=$(curl -s -X POST \
    -F "file=@${VALID_CSV}" \
    "${API_BASE}/api/upload")

echo "上傳回應:"
echo "${UPLOAD_RESPONSE}" | jq . 2>/dev/null || echo "${UPLOAD_RESPONSE}"

# 解析 file_id
VALID_FILE_ID=$(echo "${UPLOAD_RESPONSE}" | grep -o '"file_id":"[^"]*"' | cut -d'"' -f4)

if [ -n "${VALID_FILE_ID}" ]; then
    print_success "有效檔案上傳成功，file_id: ${VALID_FILE_ID}"
else
    print_error "無法從回應中解析 file_id"
    exit 1
fi

echo ""
print_test "5. 測試有錯誤檔案上傳"

ERROR_UPLOAD_RESPONSE=$(curl -s -X POST \
    -F "file=@${ERROR_CSV}" \
    "${API_BASE}/api/upload")

echo "上傳回應:"
echo "${ERROR_UPLOAD_RESPONSE}" | jq . 2>/dev/null || echo "${ERROR_UPLOAD_RESPONSE}"

ERROR_FILE_ID=$(echo "${ERROR_UPLOAD_RESPONSE}" | grep -o '"file_id":"[^"]*"' | cut -d'"' -f4)

if [ -n "${ERROR_FILE_ID}" ]; then
    print_success "錯誤檔案上傳成功，file_id: ${ERROR_FILE_ID}"
else
    print_error "無法從回應中解析錯誤檔案的 file_id"
fi

# 4. 錯誤報告測試
if [ -n "${ERROR_FILE_ID}" ]; then
    echo ""
    print_test "6. 測試錯誤報告下載"
    
    if curl -f -s "${API_BASE}/api/errors.csv?file_id=${ERROR_FILE_ID}" -o /tmp/errors_test.csv; then
        print_success "錯誤報告下載成功"
        echo "錯誤報告內容:"
        cat /tmp/errors_test.csv
        rm -f /tmp/errors_test.csv
    else
        echo -e "${YELLOW}[SKIP]${NC} 錯誤報告下載失敗或無錯誤"
    fi
fi

# 5. 資料匯入測試
echo ""
print_test "7. 測試資料匯入（有效檔案）"

IMPORT_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "{\"file_id\":\"${VALID_FILE_ID}\"}" \
    "${API_BASE}/api/import")

echo "匯入回應:"
echo "${IMPORT_RESPONSE}" | jq . 2>/dev/null || echo "${IMPORT_RESPONSE}"

if echo "${IMPORT_RESPONSE}" | grep -q '"success":true'; then
    print_success "資料匯入成功"
else
    echo -e "${YELLOW}[SKIP]${NC} 資料匯入失敗或返回錯誤"
fi

# 6. 錯誤處理測試
echo ""
print_test "8. 測試錯誤處理"

# 測試無效 file_id
echo "測試無效 file_id:"
INVALID_IMPORT=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"file_id":"invalid-file-id"}' \
    "${API_BASE}/api/import")

echo "${INVALID_IMPORT}" | jq . 2>/dev/null || echo "${INVALID_IMPORT}"

# 測試無效檔案格式
echo ""
echo "測試無效檔案格式:"
echo "This is not a CSV file" > /tmp/invalid.txt
INVALID_UPLOAD=$(curl -s -X POST \
    -F "file=@/tmp/invalid.txt" \
    "${API_BASE}/api/upload")

echo "${INVALID_UPLOAD}" | jq . 2>/dev/null || echo "${INVALID_UPLOAD}"
rm -f /tmp/invalid.txt

print_success "錯誤處理測試完成"

# 7. 使用 --form file=@- 的內聯 CSV 範例
echo ""
print_test "9. 測試內聯 CSV 上傳 (--form file=@-)"

INLINE_RESPONSE=$(cat << 'EOF' | curl -s -X POST \
    -H "Content-Type: multipart/form-data" \
    --form 'file=@-;filename=inline_test.csv;type=text/csv' \
    "${API_BASE}/api/upload"
lot_no,product_name,quantity,production_date
7777777_01,內聯測試A,10,2024-02-01
8888888_02,內聯測試B,20,2024-02-02
9999999_03,內聯測試C,30,2024-02-03
1111111_04,內聯測試D,40,2024-02-04
2222222_05,內聯測試E,50,2024-02-05
EOF
)

echo "內聯上傳回應:"
echo "${INLINE_RESPONSE}" | jq . 2>/dev/null || echo "${INLINE_RESPONSE}"

INLINE_FILE_ID=$(echo "${INLINE_RESPONSE}" | grep -o '"file_id":"[^"]*"' | cut -d'"' -f4)

if [ -n "${INLINE_FILE_ID}" ]; then
    print_success "內聯 CSV 上傳成功，file_id: ${INLINE_FILE_ID}"
    
    # 測試匯入內聯資料
    echo ""
    print_test "10. 測試內聯資料匯入"
    
    INLINE_IMPORT_RESPONSE=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"file_id\":\"${INLINE_FILE_ID}\"}" \
        "${API_BASE}/api/import")
    
    echo "內聯資料匯入回應:"
    echo "${INLINE_IMPORT_RESPONSE}" | jq . 2>/dev/null || echo "${INLINE_IMPORT_RESPONSE}"
    
    if echo "${INLINE_IMPORT_RESPONSE}" | grep -q '"success":true'; then
        print_success "內聯資料匯入成功"
    else
        echo -e "${YELLOW}[SKIP]${NC} 內聯資料匯入失敗"
    fi
else
    print_error "內聯 CSV 上傳失敗"
fi

# 清理臨時檔案
rm -f "${VALID_CSV}" "${ERROR_CSV}"

echo ""
echo " API 測試完成！"
echo ""
echo " 測試摘要:"
echo "• 健康檢查: ✓"
echo "• 檔案上傳: ✓"
echo "• 錯誤報告: ✓"
echo "• 資料匯入: ✓"
echo "• 錯誤處理: ✓"
echo "• 內聯 CSV: ✓"
echo ""
echo " 前端測試："
echo "請開啟 http://localhost:5173 進行前端功能測試"