# P2/P3 資料庫關聯問題調查報告

**日期**：2026-01-12  
**問題描述**：p2_records 有 20 筆資料，但 p3_records 只有 1 筆，需要修復關聯關係

## 1. 資料庫現況調查

### 1.1 資料表筆數統計
```
表名            | 筆數  | 說明
---------------|------|-----
p1_records     | ?    | （未查詢）
p2_records     | 20   | 所有記錄都是 lot_no=2507173_02
p2_items       | 20   | 每個 record 1 個 item
p3_records     | 1    | 只有 lot_no=2507173_02
p3_items       | 16   | 分屬兩個 lot_no
```

### 1.2 P3 資料詳細分析

#### p3_records 內容
```sql
SELECT id, lot_no_raw, lot_no_norm, created_at 
FROM p3_records;

結果：
id: ab7f43a2-396a-4ffe-ae23-47d5b1987457
lot_no_raw: 2507173_02
lot_no_norm: 250717302
created_at: 2026-01-09 06:30:04.779539+00
```

#### p3_items 統計
```sql
SELECT lot_no, COUNT(*) FROM p3_items GROUP BY lot_no;

結果：
lot_no        | count
--------------|------
2507173_02    | 12    (有對應的 p3_records)
2507243_01    | 4     (無對應的 p3_records) ⚠️
```

### 1.3 P2 資料概況
```sql
SELECT DISTINCT lot_no_raw FROM p2_records;

結果：所有 20 筆都是 2507173_02
```

## 2. 問題根本原因

### 2.1 雙重匯入路徑
系統存在兩種資料匯入路徑：

1. **Legacy 路徑**（舊系統）
   - 寫入路徑：`records` + `p3_items`
   - 檔案：`app/api/routes.py`（舊 API）
   - **問題**：只建立 `p3_items`，未同步建立 `p3_records`

2. **V2 路徑**（新系統）
   - 寫入路徑：`p3_records`（可能同步建立 `p3_items`）
   - 檔案：`app/services/import_v2.py`
   - 狀態：僅部分資料使用此路徑

### 2.2 資料不一致
```
lot_no: 2507173_02
  ✓ p3_records: 1 筆
  ✓ p3_items: 12 筆
  ✓ p2_records: 20 筆
  → 關聯完整

lot_no: 2507243_01
  ✗ p3_records: 0 筆  <-- 缺失
  ✓ p3_items: 4 筆
  ? p2_records: 未知
  → 關聯不完整
```

## 3. 影響範圍

### 3.1 受影響功能
1. **生產追溯 API**（`/api/traceability/product/{product_id}`）
   - 會先查 `p3_items`，查不到再 fallback 到 `p3_records`
   - **影響**：部分產品無法正確追溯到批次資訊

2. **UT API**（`/api/v2/ut/flatten?location=P3`）
   - 使用 `p3_items` 表查詢
   - **影響**：無（目前正常運作）

3. **P1+P2+P3 組合查詢**
   - 依賴 `p3_items` → `p2_records` → `p1_records` 追溯
   - **影響**：lot_no=2507243_01 的追溯可能中斷

### 3.2 資料完整性風險
- 未來若其他 API 依賴 `p3_records` 表，會遺漏 lot_no=2507243_01 的資料
- 報表統計可能不準確

## 4. 解決方案

### 方案 A：補齊 p3_records（推薦）
**目標**：為 `p3_items` 中的每個 lot_no 建立對應的 `p3_records` 記錄

**步驟**：
1. 查詢 `p3_items` 中所有缺失的 lot_no
2. 從 `p3_items` 彙總資訊（lot_no, production_date, tenant_id 等）
3. 建立 `p3_records` 記錄
4. 更新 `p3_items.record_id` 指向新建的 record

**SQL 範例**：
```sql
-- 1. 找出缺失的 lot_no
SELECT DISTINCT lot_no 
FROM p3_items 
WHERE record_id IS NULL 
   OR record_id NOT IN (SELECT id FROM p3_records);

-- 2. 為每個 lot_no 建立 p3_records（需要 Python 腳本執行）
INSERT INTO p3_records (
    id, tenant_id, lot_no_raw, lot_no_norm, 
    schema_version_id, extras, created_at, updated_at
)
SELECT 
    gen_random_uuid(),
    (SELECT id FROM tenants LIMIT 1),  -- 假設單租戶
    lot_no,
    CAST(REPLACE(REPLACE(lot_no, '_', ''), '-', '') AS BIGINT),
    NULL,
    jsonb_build_object(
        'production_date', MIN(production_date)::text
    ),
    MIN(created_at),
    NOW()
FROM p3_items
WHERE lot_no = '2507243_01'
GROUP BY lot_no;

-- 3. 更新 p3_items.record_id
UPDATE p3_items
SET record_id = (
    SELECT id FROM p3_records 
    WHERE lot_no_raw = p3_items.lot_no
)
WHERE lot_no = '2507243_01';
```

**優點**：
- 確保資料一致性
- 支援所有依賴 `p3_records` 的功能
- 不影響現有資料

**缺點**：
- 需要執行資料庫遷移腳本
- 需要確認 extras 欄位內容

### 方案 B：統一使用 p3_items 表
**目標**：廢棄 `p3_records`，全面改用 `p3_items` 查詢

**步驟**：
1. 修改所有 API 查詢邏輯，優先使用 `p3_items`
2. 將 `p3_records` 中的資料遷移到 `p3_items`（如果有獨有資料）
3. 標記 `p3_records` 為 deprecated

**優點**：
- 簡化資料模型
- 避免雙重維護

**缺點**：
- 需要大規模修改程式碼
- 可能影響現有功能
- 違反 V2 架構設計

### 方案 C：雙表並存，修正匯入邏輯（當前使用）
**目標**：確保未來匯入同時寫入兩個表

**步驟**：
1. 修改 legacy 匯入邏輯，同時建立 `p3_records` 和 `p3_items`
2. 修改 V2 匯入邏輯，確保同步
3. 補齊現有缺失資料（執行方案 A）

**優點**：
- 保持向後相容
- 支援兩種查詢路徑

**缺點**：
- 維護複雜度高
- 資料重複儲存

## 5. 建議行動

### 立即執行（P0）
1. **建立資料修復腳本**：補齊 lot_no=2507243_01 的 `p3_records` 記錄
2. **查詢 P2 關聯**：確認 2507243_01 是否有對應的 `p2_records`

### 短期（P1）
3. **修正匯入邏輯**：
   - Legacy 路徑加入 `p3_records` 建立邏輯
   - V2 路徑確保同步建立 `p3_items`

4. **加入資料驗證**：
   - 在匯入完成後檢查 `p3_records` 和 `p3_items` 是否對應
   - 記錄 warning 日誌

### 中期（P2）
5. **統一資料路徑**：
   - 評估是否全面改用 V2 路徑
   - 廢棄 legacy 匯入邏輯

6. **建立定期檢查**：
   - Cron job 定期檢查資料一致性
   - Dashboard 顯示不一致記錄

## 6. 查詢腳本

### 檢查不一致記錄
```sql
-- 查找有 p3_items 但沒有 p3_records 的 lot_no
SELECT DISTINCT p3i.lot_no, COUNT(*) as item_count
FROM p3_items p3i
LEFT JOIN p3_records p3r ON p3r.lot_no_raw = p3i.lot_no
WHERE p3r.id IS NULL
GROUP BY p3i.lot_no;

-- 查找有 p3_records 但沒有 p3_items 的 lot_no
SELECT p3r.lot_no_raw, p3r.lot_no_norm
FROM p3_records p3r
LEFT JOIN p3_items p3i ON p3i.lot_no = p3r.lot_no_raw
WHERE p3i.id IS NULL;
```

### 檢查 P2/P3 關聯
```sql
-- 查詢有 P3 但沒有對應 P2 的 lot_no
SELECT DISTINCT p3i.lot_no
FROM p3_items p3i
LEFT JOIN p2_records p2r ON p2r.lot_no_raw = p3i.lot_no
WHERE p2r.id IS NULL;

-- 查詢有 P2 但沒有對應 P3 的 lot_no
SELECT DISTINCT p2r.lot_no_raw
FROM p2_records p2r
LEFT JOIN p3_items p3i ON p3i.lot_no = p2r.lot_no_raw
WHERE p3i.id IS NULL;
```

## 7. 結論

**核心問題**：雙重匯入路徑導致 `p3_records` 和 `p3_items` 不同步

**建議方案**：方案 A + 方案 C 組合
1. 立即補齊缺失的 `p3_records` 記錄
2. 修正匯入邏輯，確保未來不再出現不一致

**預期效果**：
- 資料完整性恢復
- 追溯功能正常運作
- 未來匯入自動同步

---

**附錄：待確認事項**
1. ☐ lot_no=2507243_01 是否有對應的 p2_records？
2. ☐ p1_records 表狀態如何？
3. ☐ 是否有其他 lot_no 存在類似問題？
4. ☐ tenant_id 如何決定？（目前假設單租戶）
5. ☐ extras 欄位需要哪些資訊？
