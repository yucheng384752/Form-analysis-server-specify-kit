# 進階查詢功能使用手冊
*版本: 1.0*
*更新日期: 2025-01-13*

## 目錄
1. [概述](#概述)
2. [基本查詢](#基本查詢)
3. [進階查詢功能](#進階查詢功能)
4. [P2 資料顯示說明](#p2-資料顯示說明)
5. [常見問題](#常見問題)

---

## 概述

Form Analysis 系統支援 P1、P2、P3 三種資料類型的查詢。本文件詳細說明進階查詢功能，特別是 P2 資料的查詢和顯示邏輯。

### 資料類型說明
- **P1**: 生產批次資料（1 個批號 = 1 筆記錄）
- **P2**: 分條檢測資料（1 個批號 = 20 個 winders = 20 筆記錄）
- **P3**: 成品檢測資料（1 個 Product_ID = 1 筆記錄）

---

## 基本查詢

### 1. 批號查詢
在查詢頁面輸入批號進行模糊搜尋：

```
輸入: 2507173
結果: 
  - P1: 1 筆（批次資料）
  - P2: 1 筆（合併後的分條資料）
  - P3: 多筆（成品資料）
```

### 2. 查詢結果展開
點擊記錄可展開查看詳細資料：
- **P1**: 顯示生產條件、材料資訊
- **P2**: 顯示 20 個 winders 的檢測資料表格
- **P3**: 顯示成品檢測項目明細

---

## 進階查詢功能

### API 端點
```
GET /api/v2/query/records/advanced
```

### 查詢參數

| 參數 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `lot_no` | string | 批號（精確或模糊） | `2507173_02` |
| `data_type` | string | 資料類型篩選 | `P1` / `P2` / `P3` |
| `specification` | string | 規格篩選 | `1000x0.5` |
| `winder_number` | string | 收卷機編號篩選 | `1` / `5` / `12` |
| `production_date_from` | string | 生產日期起始 | `2025-01-01` |
| `production_date_to` | string | 生產日期結束 | `2025-01-31` |
| `page` | integer | 頁碼 | `1` |
| `page_size` | integer | 每頁筆數 | `50` (預設) |

### 查詢範例

#### 範例 1: 查詢特定批號的所有資料
```bash
GET /api/v2/query/records/advanced?lot_no=2507173_02
```
**結果**: 返回該批號的 P1、P2、P3 資料

#### 範例 2: 只查詢 P2 資料
```bash
GET /api/v2/query/records/advanced?lot_no=2507173_02&data_type=P2
```
**結果**: 只返回 P2 資料（合併後 1 筆）

#### 範例 3: 查詢特定 winder 的 P2 資料
```bash
GET /api/v2/query/records/advanced?lot_no=2507173_02&winder_number=5
```
**結果**: 只返回 Winder #5 的資料（不合併其他 winders）

#### 範例 4: 依規格篩選
```bash
GET /api/v2/query/records/advanced?specification=1000x0.5
```
**結果**: 返回符合規格的所有批號資料

---

## P2 資料顯示說明

### P2 資料特性
- 每個批號有 **20 個 winders**（收卷機編號 1-20）
- 每個 winder 包含獨立的檢測資料
- 系統會根據查詢條件決定如何顯示

### 顯示模式

#### 模式 1: 合併顯示（預設）
**條件**: 沒有指定 `winder_number` 參數

**行為**: 
- 20 個 winders 合併為 1 筆記錄
- 展開後顯示表格，包含所有 winders 的資料
- 適用於整體檢視和比較

**API 返回結構**:
```json
{
  "data_type": "P2",
  "lot_no": "2507173_02",
  "display_name": "2507173_02",
  "winder_number": null,
  "additional_data": {
    "lot_no": "2507173_02",
    "rows": [
      {
        "winder_number": 1,
        "sheet_width": 100,
        "thickness1": 0.5,
        "appearance": 1,
        ...
      },
      {
        "winder_number": 2,
        "sheet_width": 100,
        "thickness1": 0.5,
        ...
      },
      // ... 共 20 筆
    ]
  }
}
```

**前端顯示**:
```
批號: 2507173_02
檢測資料 (20 筆)
┌────────────────┬────────────┬────────────┬──────────┐
│ winder_number  │ sheet_width│ thickness1 │ appearance│
├────────────────┼────────────┼────────────┼──────────┤
│ 1              │ 100        │ 0.5        │ 1        │
│ 2              │ 100        │ 0.5        │ 1        │
│ ...            │ ...        │ ...        │ ...      │
└────────────────┴────────────┴────────────┴──────────┘
```

#### 模式 2: 單一 Winder 顯示
**條件**: 指定 `winder_number` 參數

**行為**:
- 只返回指定 winder 的資料
- 適用於追溯特定成品的來源

**API 返回結構**:
```json
{
  "data_type": "P2",
  "lot_no": "2507173_02",
  "display_name": "2507173_02 (W5)",
  "winder_number": 5,
  "additional_data": {
    "winder_number": 5,
    "sheet_width": 100,
    "thickness1": 0.5,
    "appearance": 1,
    ...
  }
}
```

**前端顯示**:
```
批號: 2507173_02 (W5)
收卷機: 5
片材寬度: 100
厚度1: 0.5
外觀: 1
...
```

### 使用場景

| 場景 | 查詢方式 | 顯示模式 |
|------|----------|----------|
| 查看整批分條結果 | `lot_no=2507173_02` | 合併顯示（表格） |
| 追溯特定成品來源 | `lot_no=2507173_02&winder_number=5` | 單一 Winder |
| 比較不同批次 | `specification=1000x0.5` | 各批次合併顯示 |
| 檢查特定 Winder 品質 | `winder_number=5` | 所有批號的 Winder #5 |

---

## 常見問題

### Q1: 為什麼 P2 查詢結果只有 1 筆，但展開後有 20 行資料？
**A**: 這是正常行為。為了簡化查詢結果，系統將同一批號的 20 個 winders 合併為 1 筆記錄。展開後可以看到完整的表格資料。

### Q2: 如何查詢特定 winder 的資料？
**A**: 使用 `winder_number` 參數：
```bash
GET /api/v2/query/records/advanced?lot_no=2507173_02&winder_number=5
```
這樣只會返回 Winder #5 的資料，不會合併其他 winders。

### Q3: P2 資料的表格可以排序嗎？
**A**: 可以。點擊表格標題可以依該欄位排序。系統會優先顯示「NG」結果（外觀、粗邊、分條結果）。

### Q4: 為什麼有些 winder 沒有資料？
**A**: 可能原因：
1. 該 winder 未生產
2. 資料上傳時遺漏
3. 資料庫中確實沒有該 winder 的記錄

建議檢查原始 CSV 檔案或聯繫管理員。

### Q5: Product_ID 格式是什麼？
**A**: Product_ID 格式為：
```
YYYYMMDD_機台_模具_批號
或
YYYYMMDD-機台-模具-批號
```
範例: `20250902_P24_238-2_301`

系統支援底線 (`_`) 和連字號 (`-`) 兩種分隔符號。

### Q6: 如何追溯成品的來源？
**A**: 
1. 從 P3 記錄中找到 `source_winder` 欄位（例如: 5）
2. 使用批號和 winder_number 查詢 P2:
   ```bash
   GET /api/v2/query/records/advanced?lot_no=2507173_02&winder_number=5
   ```
3. 使用批號查詢 P1:
   ```bash
   GET /api/v2/query/records/advanced?lot_no=2507173_02&data_type=P1
   ```

### Q7: 如何匯出查詢結果？
**A**: 目前版本尚未支援直接匯出功能。建議：
1. 使用 API 獲取 JSON 資料
2. 使用工具轉換為 CSV 或 Excel
3. 或等待後續版本的匯出功能

---

## 技術規格

### API 回應格式
```json
{
  "total_count": 123,
  "page": 1,
  "page_size": 50,
  "records": [
    {
      "id": "uuid",
      "lot_no": "2507173_02",
      "data_type": "P2",
      "production_date": "2025-07-17",
      "created_at": "2025-01-13T10:00:00",
      "display_name": "2507173_02",
      "winder_number": null,
      "additional_data": {
        "lot_no": "2507173_02",
        "rows": [...],
        "format": "...",
        "production_date": "..."
      }
    }
  ]
}
```

### 查詢限制
- 每頁最多 200 筆記錄
- 日期範圍最長 1 年
- 批號模糊搜尋最多返回 1000 筆

### 效能建議
1. 使用精確批號查詢優於模糊搜尋
2. 指定 `data_type` 可加快查詢速度
3. 使用分頁避免一次載入過多資料
4. 對於追溯查詢，優先使用 `winder_number` 篩選

---

## 更新日誌

### v1.0 (2025-01-13)
- 初版文件
- 說明 P2 資料合併/單一顯示邏輯
- 新增查詢範例和使用場景
- 新增常見問題解答

---

## 聯絡方式
如有問題或建議，請聯繫系統管理員或提交 Issue。
