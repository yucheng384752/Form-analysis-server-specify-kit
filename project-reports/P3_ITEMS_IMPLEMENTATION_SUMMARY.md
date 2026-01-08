# P3 Items 子表實作總結

## 概述
本次實作為 P3 資料表建立了「父子表」架構，以支援更細緻的資料查詢和追蹤功能。

## 實作日期
2025-01-XX

## 資料庫架構變更

### 1. 新增 p3_items 子表模型
**檔案**: `form-analysis-server/backend/app/models/p3_item.py`

#### 主要欄位
- `id`: UUID 主鍵
- `record_id`: 外鍵指向 records.id (CASCADE 刪除)
- `product_id`: 組合產品編號（UNIQUE 約束）
- `lot_no`: 批次號
- `machine_no`: 機台編號
- `mold_no`: 模具編號
- `specification`: 規格
- `bottom_tape_lot`: 下膠編號
- `row_no`: 列序號（在同一 record 中的順序）
- `row_data`: JSONB 完整行資料
- `created_at`: 記錄建立時間（自動設置）
- `updated_at`: 記錄更新時間（自動更新）

#### 索引設計
1. `ix_p3_items_record_id_row_no`: 複合索引（record_id + row_no）
2. `ix_p3_items_lot_no_row_no`: 複合索引（lot_no + row_no）
3. `ix_p3_items_product_id`: 單獨索引（product_id）
4. `ix_p3_items_machine_no_mold_no`: 複合索引（machine_no + mold_no）
5. `ix_p3_items_bottom_tape_lot`: 單獨索引（bottom_tape_lot）

### 2. 更新 Record 模型
**檔案**: `form-analysis-server/backend/app/models/record.py`

#### 新增內容
```python
# Imports
from typing import TYPE_CHECKING
from sqlalchemy.orm import relationship

if TYPE_CHECKING:
    from app.models.p3_item import P3Item

# Relationship
p3_items: Mapped[list["P3Item"]] = relationship(
    "P3Item",
    back_populates="record",
    cascade="all, delete-orphan"
)
```

## 匯入邏輯更新

### 檔案: `form-analysis-server/backend/app/api/routes_import.py`

#### 1. 新增 P3Item 匯入
- 在處理 P3 資料時，同時寫入父表（records）和子表（p3_items）
- 為每一行 CSV 資料創建對應的 P3Item 記錄

#### 2. Product ID 生成
P3Item 的 product_id 組成邏輯：
```
格式：YYYYMMDD_XX_YY_Z
- YYYYMMDD: 生產日期
- XX: 機台編號（從 P3_No. 欄位提取）
- YY: 模具編號（從 Record 父表）
- Z: 批次號（從 P3_No. 欄位提取）

範例：20250315_05_A8_02
```

#### 3. Source Winder (卷收機編號) 提取
從 lot_no 欄位提取最後兩碼作為卷收機編號：
```python
# lot_no 格式：2507173_02_17
# 提取最後兩碼：17
if lot_no and len(lot_no) >= 2:
    last_two = lot_no[-2:]
    if last_two.isdigit():
        record.source_winder = int(last_two)
```

## 功能實現

###  完成的項目

1. **P3Items 模型創建** 
   - 完整的欄位定義
   - 5 個索引設計
   - UniqueConstraint 約束
   - Relationship 雙向關聯

2. **Record 模型更新** 
   - 添加 relationship 定義
   - TYPE_CHECKING 導入優化

3. **P3 匯入邏輯更新** 
   - 支援父子表同步寫入
   - Product ID 自動生成
   - 舊資料自動清理（CASCADE）

4. **P3 Product ID 顯示與搜尋** 
   - 已實現 product_id 欄位
   - 進階搜尋支援 product_id 模糊查詢

5. **卷收機編號提取** 
   - 從 lot_no 提取最後兩碼
   - 存儲至 source_winder 欄位

### ⏭️ 跳過的項目（需求不明確）

1. **P1 Product Date 格式轉換**
   - 原因：需求描述不明確，現有 production_date_extractor 已處理日期轉換

2. **Created_at 特殊邏輯**
   - 原因：建議新增 data_date 欄位但未明確說明與 created_at 的關係
   - 現有 production_date 欄位已滿足生產日期追蹤需求

## 資料查詢策略

### 一般搜尋（父表）
使用 `records` 表進行快速彙總查詢：
- 批號（lot_no）
- 生產日期（production_date）
- 資料類型（data_type）

### 進階搜尋（父表 + 子表）
可選擇查詢來源：
- **父表查詢**：快速取得整體資訊
- **子表查詢**（未來）：精確查詢每一列的 product_id、machine_no、mold_no 等

### 建議的未來優化
1. 創建專門的 P3 進階搜尋端點，直接查詢 p3_items 表
2. 添加聚合查詢功能（按 machine_no 統計等）
3. 實現跨表關聯查詢（P3 → P2 → P1 的追溯）

## 資料庫遷移

### 需要執行的 SQL（待實施）

```sql
-- 1. 創建 p3_items 表
CREATE TABLE p3_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    product_id VARCHAR(50) UNIQUE,
    lot_no VARCHAR(50),
    machine_no VARCHAR(50),
    mold_no VARCHAR(50),
    specification VARCHAR(100),
    bottom_tape_lot VARCHAR(50),
    row_no INTEGER NOT NULL,
    row_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 創建索引
CREATE INDEX ix_p3_items_record_id_row_no ON p3_items(record_id, row_no);
CREATE INDEX ix_p3_items_lot_no_row_no ON p3_items(lot_no, row_no);
CREATE INDEX ix_p3_items_product_id ON p3_items(product_id);
CREATE INDEX ix_p3_items_machine_no_mold_no ON p3_items(machine_no, mold_no);
CREATE INDEX ix_p3_items_bottom_tape_lot ON p3_items(bottom_tape_lot);

-- 3. 回填既有 P3 資料（可選）
-- 這個 SQL 需要根據實際的 additional_data 結構調整
INSERT INTO p3_items (record_id, row_no, row_data, lot_no, machine_no, mold_no, specification, bottom_tape_lot)
SELECT 
    r.id,
    row_number() OVER (PARTITION BY r.id ORDER BY r.created_at),
    row_item::jsonb,
    row_item->>'lot',
    row_item->>'Machine NO',
    row_item->>'Mold NO',
    row_item->>'Specification',
    row_item->>'Bottom Tape'
FROM records r
CROSS JOIN LATERAL jsonb_array_elements(r.additional_data->'rows') AS row_item
WHERE r.data_type = 'P3';
```

## 測試建議

### 1. 單元測試
- [ ] P3Item 模型創建測試
- [ ] Relationship 關聯測試
- [ ] Cascade 刪除測試

### 2. 整合測試
- [ ] P3 CSV 匯入測試
- [ ] Product ID 生成測試
- [ ] Source Winder 提取測試
- [ ] 搜尋功能測試

### 3. 性能測試
- [ ] 大量 P3 資料匯入測試
- [ ] 索引效能測試
- [ ] 跨表查詢效能測試

## 回滾計畫

如果需要回滾此變更：

1. 停止應用服務
2. 執行 SQL：
   ```sql
   DROP TABLE IF EXISTS p3_items CASCADE;
   ```
3. 移除程式碼變更：
   - 刪除 `app/models/p3_item.py`
   - 還原 `app/models/record.py`
   - 還原 `app/api/routes_import.py`
4. 重新啟動應用

## 注意事項

1. **資料一致性**：確保匯入過程中父表和子表同步寫入
2. **外鍵約束**：刪除 Record 會自動刪除相關的 P3Item（CASCADE）
3. **Product ID 唯一性**：確保生成的 product_id 不會重複
4. **索引維護**：定期檢查索引使用情況並優化

## 參考文件

- [表單適配指南](./docs/NEW_FORM_ADAPTATION_GUIDE.md)
- [PRD2 需求文件](./docs/PRD2.md)
- [SQLAlchemy 2.0 文件](https://docs.sqlalchemy.org/en/20/)

## 變更歷史

- 2025-01-XX: 初版完成
  - 創建 P3Item 模型
  - 更新 Record 模型 relationship
  - 實作 P3 匯入邏輯
  - 添加 source_winder 提取
  - Product ID 自動生成

---

**實作者**: GitHub Copilot  
**審核狀態**: 待審核  
**部署狀態**: 待部署
