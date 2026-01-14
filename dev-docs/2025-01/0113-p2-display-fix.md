# P2 Display Fix Report - P2 顯示問題修正報告
*日期: 2025-01-13*
*類型: Bug Fix*

## 問題描述

### 症狀
一般查詢時，前端可以正確顯示 P1 和 P3 資料，但 P2 資料無法顯示，即使 API 已經返回資料。

### 問題分析

#### 1. 前端期望的資料結構
前端 `QueryPage.tsx` 中的 `renderP2ExpandedContent()` 函數期望以下資料結構：

```typescript
record.additional_data = {
  rows: [
    { winder_number: 1, field1: value1, field2: value2, ... },
    { winder_number: 2, field1: value1, field2: value2, ... },
    // ... 20 個 winder 的資料
  ]
}
```

**關鍵程式碼** ([QueryPage.tsx#L869](../../frontend/src/pages/QueryPage.tsx#L869)):
```typescript
const rows = record.additional_data.rows || [];
const sortedRows = sortRowsNgFirst(rows, ['striped results', 'Striped results', '分條結果']);
```

#### 2. 後端實際返回的資料結構
V2 API (`routes_query_v2.py`) 的 `_merge_p2_records()` 函數原本返回：

```python
additional_data = {
  'lot_no': '2507173_02',
  'winders': [  # ❌ 錯誤: 前端期望 'rows'，不是 'winders'
    {
      'winder_number': 1,
      'data': { field1: value1, field2: value2, ... }  # ❌ 資料被包裝在 'data' 內
    },
    {
      'winder_number': 2,
      'data': { field1: value1, field2: value2, ... }
    },
    // ...
  ]
}
```

#### 3. 資料庫結構
P2Record 表結構：
- 每個批號 (lot_no) 有 20 筆記錄（winder_number 1-20）
- 每筆記錄的 `extras` 欄位（JSONB）包含該 winder 的所有檢測資料
- `extras` 是扁平的 dict，例如：
  ```python
  {
    "product_name": "...",
    "sheet_width": 100.0,
    "thickness1": 0.5,
    "appearance": 1,
    # ... 其他欄位
  }
  ```

## 修正方法

### 修改檔案
- [routes_query_v2.py](../../backend/app/api/routes_query_v2.py#L174-L230)

### 修正內容

將 `_merge_p2_records()` 函數修改為：

```python
def _merge_p2_records(records: list[P2Record]) -> list[QueryRecordV2Compat]:
    """將相同 lot_no 的 P2 Records (20個winders) 合併成單一筆查詢記錄
    
    前端期望的資料結構是 additional_data.rows 陣列，每個 row 是扁平的 dict。
    """
    from collections import defaultdict
    
    # 按 lot_no_norm 分組
    grouped = defaultdict(list)
    for r in records:
        grouped[r.lot_no_norm].append(r)
    
    merged_results = []
    for lot_no_norm, lot_records in grouped.items():
        # 排序確保 winder 順序一致
        lot_records.sort(key=lambda x: x.winder_number)
        
        first = lot_records[0]
        row0 = _first_row(first.extras)
        
        # ✅ 修正: 將每個 winder 的 extras 直接展開為 row
        rows = []
        for rec in lot_records:
            if isinstance(rec.extras, dict):
                row = rec.extras.copy()
                row['winder_number'] = rec.winder_number  # 確保包含 winder_number
                rows.append(row)
        
        # ✅ 修正: 使用 'rows' 欄位名稱
        merged_extras = {
            'lot_no': first.lot_no_raw,
            'rows': rows  # 前端期望此欄位名稱
        }
        
        # 從第一個 winder 提取共同資訊
        if isinstance(first.extras, dict):
            for key in ['format', 'Format', '規格', 'production_date', 'Production Date', '生產日期']:
                if key in first.extras:
                    merged_extras[key] = first.extras[key]
        
        merged_results.append(QueryRecordV2Compat(
            id=str(first.id),
            lot_no=first.lot_no_raw,
            data_type='P2',
            production_date=_extract_production_date_from_row(row0),
            created_at=first.created_at.isoformat(),
            display_name=first.lot_no_raw,
            winder_number=None,
            additional_data=merged_extras,
        ))
    
    return merged_results
```

### 關鍵變更

1. **資料結構變更**: `winders` → `rows`
   - 前端期望 `additional_data.rows`
   - 舊版使用 `additional_data.winders` 導致前端無法識別

2. **資料展開**: 移除 `{winder_number, data}` 包裝
   - 前端期望每個 row 是扁平的 dict
   - 舊版將資料包裝在 `data` 欄位內，前端無法直接存取欄位

3. **欄位注入**: 確保 `winder_number` 包含在每個 row 中
   - 方便前端顯示和追溯

## 修正前後對比

### 修正前
```json
{
  "data_type": "P2",
  "lot_no": "2507173_02",
  "additional_data": {
    "winders": [
      {
        "winder_number": 1,
        "data": {
          "sheet_width": 100,
          "thickness1": 0.5
        }
      }
    ]
  }
}
```
**結果**: 前端找不到 `rows` 欄位，無法顯示資料

### 修正後
```json
{
  "data_type": "P2",
  "lot_no": "2507173_02",
  "additional_data": {
    "rows": [
      {
        "winder_number": 1,
        "sheet_width": 100,
        "thickness1": 0.5
      }
    ]
  }
}
```
**結果**: 前端可以正確渲染 P2 表格

## 驗證方法

### 1. API 測試
使用 curl 或 Postman 測試 API 端點：

```bash
# 基本查詢（會觸發 P2 合併邏輯）
curl -X GET "http://localhost:18002/api/v2/query/records/advanced?lot_no=2507173_02" \
  -H "X-Tenant-Id: <your-tenant-id>"

# 檢查回應結構
# ✓ 確認 P2 記錄存在
# ✓ 確認 additional_data.rows 陣列存在
# ✓ 確認 rows 包含 20 筆資料（或實際 winder 數量）
# ✓ 確認每個 row 是扁平的 dict，包含 winder_number 欄位
```

### 2. 前端測試
1. 啟動前端服務: `http://localhost:18003`
2. 進入「資料查詢」頁面
3. 輸入批號查詢，例如: `2507173_02`
4. 驗證結果:
   - ✓ P1 資料正常顯示
   - ✓ P2 資料正常顯示（之前無法顯示）
   - ✓ P3 資料正常顯示
5. 展開 P2 記錄，檢查:
   - ✓ 顯示表格，包含所有 winder 的資料
   - ✓ 表格可排序
   - ✓ 資料欄位正確顯示

### 3. 整合測試腳本
執行提供的測試腳本：

```powershell
cd form-analysis-server
powershell -ExecutionPolicy Bypass -File test-p2-display.ps1
```

**期望輸出**:
```
P2 Display Fix Integration Test
========================================
Test 1: Basic Query API
Lot No: 2507173_02
API Response OK
  Total Count: X
  Records Returned: Y

Data Type Statistics:
  P1: 1 records
  P2: 1 records  # 合併後只有 1 筆
  P3: Z records

Test 2: Check P2 Data Structure
OK: additional_data exists
OK: additional_data.rows exists
  Rows Count: 20  # 20 個 winders
OK: rows array contains data
OK: Contains winder_number: 1

Test Summary: All tests passed
```

## 相關議題

### 條件合併邏輯
當使用 **winder_number 篩選** 時，P2 不會合併，而是返回單一 winder 的資料：

```python
# routes_query_v2.py#L670-L693
if winder_filter_applied:
    # 只顯示指定的 winder，不合併其他 19 個
    for rec in p2_records:
        records.append(_p2_to_query_record(rec))
else:
    # 沒有 winder 篩選時，合併相同批號的 records（20個 winders → 1筆）
    merged_p2 = _merge_p2_records(p2_records)
    records.extend(merged_p2)
```

**說明**:
- 一般查詢: 20 個 winders 合併為 1 筆記錄，前端顯示表格
- 指定 winder 查詢: 只返回該 winder 的資料，前端顯示該 winder 詳情

## 影響範圍

### 修改影響
- **API**: routes_query_v2.py 的 `_merge_p2_records()` 函數
- **前端**: 無需修改（原本就期望 `rows` 格式）
- **資料庫**: 無需修改

### 向後相容性
- ✓ 不影響 P1/P3 資料顯示
- ✓ 不影響 winder 篩選功能
- ✓ 不影響舊版 API (routes_query.py)

### 風險評估
- **低風險**: 僅修改資料組裝邏輯，不涉及資料庫或業務邏輯
- **測試建議**: 在生產環境部署前，確保測試所有 P2 查詢情境

## 後續建議

1. **測試覆蓋**:
   - 新增自動化測試驗證 P2 資料結構
   - 測試有/無 winder 篩選的兩種情況

2. **文檔更新**:
   - 更新 API 文檔，說明 additional_data 結構
   - 撰寫前後端資料契約文檔

3. **監控**:
   - 記錄 P2 查詢頻率和性能
   - 監控前端錯誤日誌

## Commit 資訊
- **Commit**: [待提交]
- **Branch**: [當前分支]
- **Files Changed**: 
  - `backend/app/api/routes_query_v2.py` (修改)
  - `test-p2-display.ps1` (新增)
  - `dev-docs/2025-01/0113-p2-display-fix.md` (新增)

## 參考資料
- Product_ID 格式修正: [0113-test-report.md](./0113-test-report.md)
- P2 條件合併實作: [routes_query_v2.py#L670-L693](../../backend/app/api/routes_query_v2.py#L670-L693)
- 前端渲染邏輯: [QueryPage.tsx#L864-L920](../../frontend/src/pages/QueryPage.tsx#L864-L920)
