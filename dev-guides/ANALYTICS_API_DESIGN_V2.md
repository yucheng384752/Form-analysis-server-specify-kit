# 追溯資料扁平化 API 設計文件 v2

**版本**: v2.0  
**日期**: 2026-01-12  
**新規定**: 支援多 server 並發呼叫 + 明確 null/空陣列語義

---

## **變更摘要**

### 新增規定

1. **支援多 server 同時呼叫**
   - 無全域狀態設計（每個請求獨立 session）
   - Connection pool 支援並發（10 連線 + 20 溢出）
   - Rate limiting 保護（每 IP 每分鐘 30 次請求）
   - 無資料競爭（無共享內存寫入）

2. **資料完整性語義**
   - 資料庫內沒有的值 → 填入 `null`（而非省略或預設值）
   - 空資料 → 維持空陣列 `[]`（而非 null）
   - 明確的 null vs 空陣列區別

---

## **架構設計**

### 並發處理機制

```
多個 Server 同時呼叫
    │
    ├─ Server A ──┐
    ├─ Server B ──┼── Rate Limiting (30 req/min/IP)
    └─ Server C ──┘
          │
          ▼
    FastAPI Router (無狀態)
          │
          ├─ 每個請求獨立 AsyncSession
          ├─ Connection Pool (10 base + 20 overflow)
          └─ 無全域變數寫入
          │
          ▼
    TraceabilityFlattener (無狀態類別)
          │
          ├─ 批次查詢 P1/P2/P3
          ├─ 內存映射（請求內隔離）
          └─ 扁平化合併
          │
          ▼
    PostgreSQL (MVCC 支援並發讀取)
```

### Null vs 空陣列語義

| 情況 | 回傳值 | 說明 |
|------|--------|------|
| 欄位存在且有值 | 實際值 | 如 `"P1.Material": "PET"` |
| 欄位存在但為空字串 | `""` | 空字串視為有效值 |
| 欄位不存在於資料庫 | `null` | 明確標示缺失 |
| P3.extras.rows == [] | `{"data": [], "count": 0}` | 空陣列保留 |
| 查詢無結果 | `{"data": [], "count": 0}` | 空陣列表示無資料 |

---

## **API 端點**

### 1. 按月份查詢（主要端點）

**URL**: `GET /api/v2/analytics/traceability/flatten/monthly`

**參數**:
- `year` (required): 年份（2020-2030）
- `month` (required): 月份（1-12）

**範例請求**:
```bash
curl "http://localhost:8000/api/v2/analytics/traceability/flatten/monthly?year=2025&month=9"
```

**回應格式**:
```json
{
  "data": [
    {
      "timestamp": "2025-09-01T08:00:00Z",
      "type": "P3",
      "location": "",
      "LOT NO.": "P3-20250901-001",
      "P1.Specification": "SPEC-001",
      "P1.Material": "PET",
      "Semi-finished Sheet Width(mm)": 1200.5,
      "Semi-finished Length(M)": null,
      "Weight(Kg)": 45.8,
      "Actual Temp_C1(°C)": 250.0,
      "Actual Temp_C2(°C)": null,
      "Set Temp_C1(°C)": 255.0,
      "Line Speed(M/min)": 15.5,
      "Current(A)": 120.3,
      "Machine_No.": "M001",
      "P2.Material": "BOPP",
      "Slitting date": "2025-09-02T10:30:00Z",
      "Board Width(mm)": 350.0,
      "Thicknessss High(μm)": 25.5,
      "Thicknessss Low(μm)": 24.8,
      "Production Date": "2025-09-03T14:00:00Z",
      "P3.Specification": "FINAL-001",
      "lot": "LOT-A-001",
      "Finish": "合格",
      "operator": "王小明"
    }
  ],
  "count": 850,
  "has_data": true,
  "metadata": {
    "query_type": "monthly",
    "year": 2025,
    "month": 9,
    "compression": "gzip",
    "null_handling": "explicit"
  }
}
```

**空資料範例**:
```json
{
  "data": [],
  "count": 0,
  "has_data": false,
  "metadata": {
    "query_type": "monthly",
    "year": 2025,
    "month": 12,
    "compression": "none",
    "null_handling": "explicit"
  }
}
```

---

### 2. 按產品 ID 查詢

**URL**: `GET /api/v2/analytics/traceability/flatten`

**參數**:
- `product_ids` (required): 產品 ID 列表（逗號分隔）
- 最多 500 個 ID

**範例請求**:
```bash
curl "http://localhost:8000/api/v2/analytics/traceability/flatten?product_ids=P3-20250901-001,P3-20250901-002"
```

**回應格式**: 同上

---

### 3. 健康檢查

**URL**: `GET /api/v2/analytics/traceability/health`

**回應**:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-01T12:00:00Z",
  "config": {
    "max_records_per_request": 1500,
    "rate_limit_per_minute": 30,
    "auto_gzip_threshold": 200,
    "null_handling": "explicit",
    "empty_array_handling": "preserve"
  }
}
```

---

## **壓縮策略**

### 自動壓縮閥值

| 筆數 | 壓縮 | 說明 |
|------|------|------|
| < 200 筆 | 不壓縮 | 小資料量，壓縮收益低 |
| 200-1500 筆 | **自動 gzip** | 主要場景（月度查詢） |
| 1501-3000 筆 | 強制壓縮 + 建議分頁 | 大資料量警告 |
| > 3000 筆 | **拒絕請求**（HTTP 413） | 防濫用 |

### 壓縮效果

- **原始大小**: ~1.2KB/筆 → 1500 筆 ≈ 1.8MB
- **壓縮後**: ~70% 壓縮率 → 約 540KB
- **Client 處理**: 透明解壓縮（瀏覽器/curl 自動處理）

---

## **並發安全保證**

### 1. Connection Pool 配置

```python
# backend/app/config/analytics_config.py
DB_POOL_SIZE = 10              # 基本連線池
DB_MAX_OVERFLOW = 20           # 最大溢出連線
# 支援最多 30 個並發請求
```

### 2. Rate Limiting

- **限制**: 每 IP 每分鐘 30 次請求
- **實作**: 內存計數器（生產環境建議 Redis）
- **回應**: HTTP 429 Too Many Requests

### 3. 無狀態設計

**每個請求**:
- 獨立 `AsyncSession`
- 獨立 `TraceabilityFlattener` 實例
- 獨立內存映射表（p1_map, p2_map）

**無全域狀態**:
- 無共享 cache（除 rate limit 計數）
- 無共享資料結構
- 無檔案鎖定

---

## **欄位映射邏輯**

### 完整欄位清單（70+ 欄位）

```python
OUTPUT_FIELD_ORDER = [
    # P3 核心（5 個）
    'timestamp', 'type', 'location', 'LOT NO.',
    
    # P1 追溯（32 個）
    'P1.Specification', 'P1.Material',
    'Semi-finished Sheet Width(mm)', 'Semi-finished Length(M)', 'Weight(Kg)',
    'Actual Temp_C1(°C)', ..., 'Actual Temp_C8(°C)',
    'Set Temp_C1(°C)', ..., 'Set Temp_C8(°C)',
    'Actual Temp_A bucket(°C)', 'Set Temp_A bucket(°C)',
    'Actual Temp_Top(°C)', 'Actual Temp_Mid(°C)', 'Actual Temp_Bottom(°C)',
    'Set Temp_Top(°C)', 'Set Temp_Mid(°C)', 'Set Temp_Bottom(°C)',
    'Line Speed(M/min)', 'Current(A)', 'Extruder Speed (rpm)', 'Frame (cm)',
    'Machine_No.', 'Semi_No.',
    
    # P2 追溯（13 個）
    'format', 'P2.Material', 'Semi-finished No.',
    'Slitting date', 'Slitting machine', 'Winder number',
    'Board Width(mm)', 'Thicknessss High(μm)', 'Thicknessss Low(μm)',
    'Appearance', 'rough edge', 'Striped Results',
    
    # P3 產品資訊（14 個）
    'Production Date', 'P3.Specification', 'BottomTape',
    'Machine No.', 'Mold No.', 'lot', 'AdjustmentRecord',
    'Finish', 'operator', 'Produce_No.', 'Specification',
]
```

### Null 處理範例

```python
# 情況 1: 欄位存在
P1Record.extras = {"material": "PET", "sheet_width": 1200.5}
→ {"P1.Material": "PET", "Semi-finished Sheet Width(mm)": 1200.5}

# 情況 2: 欄位不存在
P1Record.extras = {"material": "PET"}
→ {"P1.Material": "PET", "Semi-finished Sheet Width(mm)": null}

# 情況 3: P1 整筆不存在（無追溯到上游）
P1Record = None
→ 所有 P1 欄位都是 null
```

---

## **測試計畫**

### 1. 並發測試

```bash
# 同時發送 10 個請求（模擬多 server）
for i in {1..10}; do
  curl "http://localhost:8000/api/v2/analytics/traceability/flatten/monthly?year=2025&month=9" &
done
wait

# 預期結果：
# - 10 個請求都成功回應
# - 無資料競爭錯誤
# - 回應時間 < 5 秒
```

### 2. Null 語義測試

```python
# 測試案例 1: 資料完整
assert response["data"][0]["P1.Material"] == "PET"
assert response["data"][0]["Semi-finished Sheet Width(mm)"] == 1200.5

# 測試案例 2: 欄位缺失
assert response["data"][1]["Actual Temp_C2(°C)"] is None  # null
assert response["data"][1]["P1.Material"] == "BOPP"       # 其他欄位正常

# 測試案例 3: 空陣列
response = flatten_by_month(year=2099, month=12)  # 無資料月份
assert response["data"] == []
assert response["count"] == 0
assert response["has_data"] is False
```

### 3. 壓縮測試

```bash
# 小資料量（不壓縮）
curl -H "Accept-Encoding: gzip" \
     "http://localhost:8000/.../monthly?year=2025&month=1" \
     -o response.json
# 預期：Content-Encoding 不含 gzip

# 大資料量（自動壓縮）
curl -H "Accept-Encoding: gzip" \
     "http://localhost:8000/.../monthly?year=2025&month=9" \
     --compressed -o response.json
# 預期：Content-Encoding: gzip，檔案大小 < 原始 30%
```

### 4. Rate Limiting 測試

```bash
# 快速發送 31 次請求
for i in {1..31}; do
  curl "http://localhost:8000/api/v2/analytics/traceability/health"
done

# 預期：第 31 次收到 HTTP 429
```

---

## **效能指標**

### 預期效能（單次請求）

| 筆數 | 查詢時間 | 原始大小 | 壓縮後 | 壓縮率 |
|------|----------|----------|--------|--------|
| 100 筆 | ~1 秒 | 120KB | - | - |
| 500 筆 | ~2 秒 | 600KB | - | - |
| 900 筆 | ~3 秒 | 1.1MB | 330KB | 70% |
| 1500 筆 | ~4.5 秒 | 1.8MB | 540KB | 70% |
| 3000 筆 | ~8 秒 | 3.6MB | 1.1MB | 69% |

### 並發效能（10 個 server 同時呼叫）

- **Connection Pool**: 支援 30 並發
- **每個請求**: 2-5 秒獨立完成
- **總吞吐量**: ~300 筆/秒（基於 10 連線 × 30 筆/秒）

---

## **故障排查**

### HTTP 429 Too Many Requests

**原因**: 超過 rate limit（30 req/min/IP）

**解決**:
1. 降低請求頻率
2. 使用不同 IP（負載均衡）
3. 聯絡管理員調整限制

### HTTP 413 Payload Too Large

**原因**: 查詢結果超過 3000 筆

**解決**:
1. 縮小日期範圍（按月拆分）
2. 使用 product_id 過濾
3. 聯絡管理員討論分頁方案

### Null 值過多

**原因**: 上游資料缺失（P1/P2 未建立關聯）

**檢查**:
```sql
-- 檢查 P3 → P2 關聯
SELECT p3.product_id, p3.lot_no_norm, COUNT(p2.id)
FROM p3_records p3
LEFT JOIN p2_records p2 ON p3.lot_no_norm = p2.lot_no_norm
GROUP BY p3.product_id, p3.lot_no_norm
HAVING COUNT(p2.id) = 0;

-- 檢查 P2 → P1 關聯
SELECT p2.product_id, p2.lot_no_norm, COUNT(p1.id)
FROM p2_records p2
LEFT JOIN p1_records p1 ON p2.lot_no_norm = p1.lot_no_norm
GROUP BY p2.product_id, p2.lot_no_norm
HAVING COUNT(p1.id) = 0;
```

---

## **實作檔案清單**

### 已建立檔案

1. `backend/app/config/analytics_config.py`
   - 閥值設定
   - Connection pool 配置
   - Rate limiting 參數
   - Null 處理欄位清單

2. `backend/app/config/analytics_field_mapping.py`
   - 70+ 欄位映射表
   - 輸出欄位順序
   - Null 處理函數
   - 預設值配置

3. `backend/app/services/traceability_flattener.py`
   - 批次查詢邏輯
   - 扁平化合併
   - 無狀態設計
   - Null/空陣列處理

4. `backend/app/api/routes_analytics.py`
   - `/flatten/monthly` 端點
   - `/flatten` 端點（按 ID）
   - `/health` 健康檢查
   - Rate limiting 實作

5. `backend/app/main.py`（已修改）
   - 加入 GZIPMiddleware
   - 掛載 analytics 路由

---

## **啟動與測試**

### 啟動 Backend

```bash
cd form-analysis-server/backend
python -m uvicorn app.main:app --reload --port 8000
```

### 快速測試

```bash
# 1. 健康檢查
curl http://localhost:8000/api/v2/analytics/traceability/health

# 2. 查詢單月資料
curl "http://localhost:8000/api/v2/analytics/traceability/flatten/monthly?year=2025&month=9" | jq .

# 3. 檢查 null 語義
curl "..." | jq '.data[0] | to_entries | map(select(.value == null))'

# 4. 檢查壓縮
curl -I -H "Accept-Encoding: gzip" "..." | grep Content-Encoding
```

---

## **總結**

### 新規定實作狀態

| 需求 | 狀態 | 實作方式 |
|------|------|----------|
| 多 server 並發呼叫 | 完成 | 無狀態設計 + Connection pool |
| 資料庫無值 → null | 完成 | 明確 null 處理邏輯 |
| 空資料 → 空陣列 | 完成 | 保留 `[]` 不轉 null |
| Rate limiting | 完成 | 30 req/min/IP |
| 自動壓縮 | 完成 | Gzip ≥200 筆 |

### 關鍵特性

- **並發安全**: 無資料競爭，支援 30 並發連線
- **明確語義**: null 表示缺失，空陣列表示無資料
- **自動優化**: 200+ 筆自動壓縮 70%
- **防濫用**: Rate limiting + 筆數上限
- **生產就緒**: 健康檢查 + 錯誤處理
