# 資料架構重構總結 (2026-01-13)

## 📋 需求

將匯入和查詢邏輯改為**混合架構**：
- **P1**: 儲存在 `p1_records` 表 (原設計，無變更)
- **P2**: 1筆 `p2_records` (主表) + 20筆 `p2_items_v2` (明細表)
- **P3**: 1筆 `p3_records` (主表) + N筆 `p3_items_v2` (明細表)

## ✅ 已完成的修改

### 1. 資料庫表結構 ✅

建立了兩個新表：

#### `p2_items_v2`
- **用途**: 儲存P2每個winder的展開資料
- **外鍵**: `p2_record_id` → `p2_records.id`
- **主要欄位**: winder_number, sheet_width, thickness1-7, appearance, rough_edge, slitting_result, row_data (JSONB)
- **唯一約束**: (p2_record_id, winder_number)

#### `p3_items_v2`
- **用途**: 儲存P3每筆生產明細
- **外鍵**: `p3_record_id` → `p3_records.id`
- **主要欄位**: row_no, product_id, lot_no, production_date, machine_no, mold_no, production_lot, source_winder, specification, bottom_tape_lot, row_data (JSONB)
- **唯一約束**: (p3_record_id, row_no)

**SQL 檔案**: [backend/migrations/create_items_v2_tables.sql](backend/migrations/create_items_v2_tables.sql)

### 2. ORM Model ✅

建立新 Model 檔案：
- **`app/models/p2_item_v2.py`**: P2ItemV2 class
- **`app/models/p3_item_v2.py`**: P3ItemV2 class

更新現有 Model 添加 relationship:
- **`app/models/p2_record.py`**: 添加 `items_v2` relationship
- **`app/models/p3_record.py`**: 添加 `items_v2` relationship

### 3. Import V2 服務邏輯 ✅

修改 `app/services/import_v2.py` 的 `commit_job()` 方法：

#### P2 匯入流程 (lines ~380-430)
```python
# 1. 建立或取得 P2Record (lot level, winder_number=0)
# 2. 刪除舊的 P2ItemV2
# 3. 為每個 winder 建立 P2ItemV2 (20筆)
#    - 從 row_data 提取 winder_number
#    - 儲存 sheet_width, thickness1-7, appearance 等欄位
#    - 保留完整 row_data (JSONB)
```

#### P3 匯入流程 (lines ~431-530)
```python
# 1. 建立或取得 P3Record (batch level)
# 2. 刪除舊的 P3ItemV2
# 3. 為每個 row 建立 P3ItemV2 (N筆)
#    - 提取 product_id, lot_no, production_date 等
#    - 儲存結構化欄位
#    - 保留完整 row_data (JSONB)
```

### 4. Query V2 路由邏輯 ✅

修改 `app/api/routes_query_v2.py` 的查詢端點：

#### P2 查詢 (lines ~755-782)
```python
# 1. 使用 selectinload(P2Record.items_v2) 預載 items
# 2. JOIN P2ItemV2 進行 specification 和 winder 篩選
# 3. 呼叫 _p2_to_query_record_with_items() 組合結果
# 4. 返回 additional_data.rows 格式 (前端期望)
```

#### P3 查詢 (lines ~823-855)
```python
# 1. 使用 selectinload(P3Record.items_v2) 預載 items
# 2. JOIN P3ItemV2 進行 specification 和 source_winder 篩選
# 3. 呼叫 _p3_to_query_record_with_items() 組合結果
# 4. 返回 additional_data.rows 格式
```

新增轉換函數：
- **`_p2_to_query_record_with_items()`**: 組合 P2Record + items → rows 格式
- **`_p3_to_query_record_with_items()`**: 組合 P3Record + items → rows 格式

## 📊 資料流程

### 匯入流程
```
CSV File
  ↓
Import V2 API
  ↓
Parse → Staging Rows
  ↓
Validate
  ↓
Commit:
  - P1: 1筆 p1_records (extras.rows = all rows)
  - P2: 1筆 p2_records + 20筆 p2_items_v2 (per winder)
  - P3: 1筆 p3_records + N筆 p3_items_v2 (per product)
```

### 查詢流程
```
Query API (/api/v2/query/records/advanced)
  ↓
篩選條件 (lot_no, date, machine, mold, specification, winder)
  ↓
查詢:
  - P1: SELECT from p1_records
  - P2: SELECT p2_records JOIN p2_items_v2
  - P3: SELECT p3_records JOIN p3_items_v2
  ↓
組合 records + items → additional_data.rows
  ↓
返回 QueryResponseV2Compat
```

## 🔄 與舊架構的差異

| 項目 | 舊架構 (已棄用) | 新架構 (混合模式) |
|------|----------------|------------------|
| **P2 儲存** | 20筆 p2_records (per winder) <br/> extras = 完整 row data | 1筆 p2_records (summary) <br/> + 20筆 p2_items_v2 (per winder) |
| **P3 儲存** | 1筆 p3_records <br/> extras.rows = all products | 1筆 p3_records (batch) <br/> + N筆 p3_items_v2 (per product) |
| **P2 查詢** | 查詢 p2_records，合併20筆 | 查詢 p2_records JOIN p2_items_v2 |
| **P3 查詢** | 查詢 p3_records，從 extras 提取 | 查詢 p3_records JOIN p3_items_v2 |
| **篩選** | 在 JSONB extras 中搜尋 | 在結構化欄位中搜尋 (更快) |
| **擴展性** | 難以添加新欄位 | ✅ 可添加 p*_items_v2 欄位 |

## 🧪 測試步驟

### 1. 匯入測試資料

```bash
# 使用前端 UI 或 API 匯入
POST /api/v2/import/jobs
Content-Type: multipart/form-data

Body:
- table_code: P2
- files: P2_2507173_02.csv
```

### 2. 驗證資料庫

```sql
-- 檢查 P2 資料
SELECT COUNT(*) FROM p2_records;  -- 應為 1 (每批號)
SELECT COUNT(*) FROM p2_items_v2; -- 應為 20 (20個winders)

-- 檢查 P3 資料
SELECT COUNT(*) FROM p3_records;  -- 應為 1 (每批次)
SELECT COUNT(*) FROM p3_items_v2; -- 應為 N (N個產品)

-- 檢查關聯
SELECT p2r.lot_no_raw, COUNT(p2i.id) as item_count
FROM p2_records p2r
LEFT JOIN p2_items_v2 p2i ON p2r.id = p2i.p2_record_id
GROUP BY p2r.id, p2r.lot_no_raw;
```

### 3. 測試 API 查詢

```bash
# 一般查詢 (應返回合併的 P2 資料)
curl "http://localhost:18002/api/v2/query/records/advanced?lot_no=2507173_02"

# Winder 篩選 (應只返回指定 winder)
curl "http://localhost:18002/api/v2/query/records/advanced?lot_no=2507173_02&winder_number=5"

# 規格篩選
curl "http://localhost:18002/api/v2/query/records/advanced?specification=0.32mm"
```

### 4. 驗證前端顯示

開啟 http://localhost:18003:
- [ ] 查詢批號，P2 資料顯示為表格 (20 rows)
- [ ] P2 表格可排序
- [ ] P3 資料顯示為列表 (N products)
- [ ] 欄位顯示完整

## 📁 修改的檔案清單

### 新增檔案
- `backend/migrations/create_items_v2_tables.sql` - 資料表建立 SQL
- `backend/app/models/p2_item_v2.py` - P2 Items Model
- `backend/app/models/p3_item_v2.py` - P3 Items Model

### 修改檔案
- `backend/app/models/p2_record.py` - 添加 items_v2 relationship
- `backend/app/models/p3_record.py` - 添加 items_v2 relationship
- `backend/app/services/import_v2.py` - P2/P3 匯入邏輯改為主表+明細表模式
- `backend/app/api/routes_query_v2.py` - 查詢邏輯改為 JOIN items_v2 表

## ⚠️ 注意事項

1. **向後相容性**: 保留了 `_p2_to_query_record()` 和 `_p3_to_query_record()` 作為 fallback
2. **舊資料**: Legacy 表 (`p2_items`, `p3_items`) 仍保留，不影響舊資料
3. **API 端點**: 無變更，前端無需修改
4. **回傳格式**: 保持 `additional_data.rows` 格式，前端無感知
5. **Tenant**: 所有 items_v2 都包含 tenant_id，支援多租戶

## 🚀 後續建議

1. ✅ **完成測試**: 匯入實際資料驗證功能
2. ⏳ **前端驗證**: 確認 P2/P3 表格正確顯示
3. ⏳ **性能測試**: 大量資料下的查詢效能
4. ⏳ **文檔更新**: 更新 API 文檔說明新架構
5. ⏳ **Legacy 清理**: 確認無使用後可考慮移除舊 items 表

## 📌 關鍵優勢

✅ **結構化查詢**: 可直接在欄位上建立索引，查詢更快
✅ **資料完整性**: 外鍵約束確保資料一致性
✅ **擴展性**: 易於添加新欄位而不影響 JSONB 結構
✅ **可維護性**: 清晰的主從關係，易於理解和維護
✅ **查詢彈性**: 支援複雜篩選條件 (specification, winder, source_winder)
