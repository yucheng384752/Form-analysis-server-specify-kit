# 資料庫遷移錯誤修復報告 - 完整解決方案

## 問題摘要
**錯誤類型**: SQLAlchemy 資料庫遷移錯誤
**主要錯誤**: 
1. `column records.data_type does not exist`
2. `current transaction is aborted, commands ignored until end of transaction block`

**發生位置**: 檔案匯入功能 - UploadPage.tsx:587

## 根本原因分析

### 1. 資料庫結構不一致
- **模型定義**: `app/models/record.py` 包含完整的 P1/P2/P3 欄位定義
- **實際表結構**: `records` 表缺少 `data_type` 及其他 P1/P2/P3 相關欄位
- **遷移狀態**: Alembic 顯示遷移已執行，但實際資料庫結構未更新

### 2. 遷移執行問題
遷移檔案 `2025_11_10_0110-d0c4b28c0776_add_p1_p2_p3_data_types.py` 中的變更沒有正確應用到資料庫

### 3. 事務錯誤連鎖反應
缺少 `data_type` 欄位導致 SQL 查詢失敗，進而造成事務中止，後續的狀態更新也失敗

## 完整解決方案

### 階段 1: 資料庫結構修復
1. **添加 data_type 欄位**:
   ```sql
   ALTER TABLE records ADD COLUMN IF NOT EXISTS data_type data_type_enum;
   ```

2. **設置現有記錄的預設值**:
   ```sql
   UPDATE records SET data_type = 'P1' WHERE data_type IS NULL;
   ```

3. **設置欄位為非空**:
   ```sql
   ALTER TABLE records ALTER COLUMN data_type SET NOT NULL;
   ```

### 階段 2: P1/P2/P3 專用欄位添加
```sql
-- P1/P3 共用欄位
ALTER TABLE records ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS p3_no VARCHAR(50);

-- P2 專用欄位  
ALTER TABLE records ADD COLUMN IF NOT EXISTS sheet_width FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS thickness1 FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS thickness2 FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS thickness3 FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS thickness4 FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS thickness5 FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS thickness6 FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS thickness7 FLOAT;
ALTER TABLE records ADD COLUMN IF NOT EXISTS appearance INTEGER;
ALTER TABLE records ADD COLUMN IF NOT EXISTS rough_edge INTEGER;
ALTER TABLE records ADD COLUMN IF NOT EXISTS slitting_result INTEGER;

-- 通用額外資料存儲
ALTER TABLE records ADD COLUMN IF NOT EXISTS additional_data JSONB;
```

### 階段 3: 欄位約束調整
```sql
-- 將原有必填欄位改為可選，支援不同資料類型
ALTER TABLE records ALTER COLUMN production_date DROP NOT NULL;
ALTER TABLE records ALTER COLUMN product_name DROP NOT NULL;
ALTER TABLE records ALTER COLUMN quantity DROP NOT NULL;
```

### 階段 4: 索引創建
```sql
-- 為查詢優化創建索引
CREATE INDEX IF NOT EXISTS ix_records_data_type ON records USING btree (data_type);
CREATE INDEX IF NOT EXISTS ix_records_lot_no_data_type ON records USING btree (lot_no, data_type);
```

### 階段 5: 服務重啟
- 重新啟動 backend 服務以載入新的資料庫結構

## 驗證結果

### 資料庫結構確認
```
records 表現在包含:
✓ data_type (data_type_enum, NOT NULL)
✓ notes (TEXT, nullable)  
✓ p3_no (VARCHAR(50), nullable)
✓ sheet_width (FLOAT, nullable)
✓ thickness1-7 (FLOAT, nullable) 
✓ appearance, rough_edge, slitting_result (INTEGER, nullable)
✓ additional_data (JSONB, nullable)
```

### 索引和約束
```
✓ ix_records_data_type (data_type)
✓ ix_records_lot_no_data_type (lot_no, data_type)  
✓ production_date, product_name, quantity 改為可選
```

### 服務狀態
```
✓ PostgreSQL: 健康運行 (Port 18001)
✓ FastAPI Backend: 健康運行 (Port 18002)
✓ React Frontend: 健康運行 (Port 18003)
✓ API 端點: 全部可訪問
```

## 支援的資料類型

### P1 - 產品基本資料
- `lot_no`: 批號
- `product_name`: 產品名稱  
- `quantity`: 數量
- `production_date`: 生產日期
- `notes`: 備註
- `additional_data`: 其他 CSV 欄位的 JSON 存儲

### P2 - 尺寸檢測資料  
- `lot_no`: 批號
- `sheet_width`: 片材寬度(mm)
- `thickness1-7`: 厚度測量值(μm)
- `appearance`: 外觀檢查結果
- `rough_edge`: 粗糙邊緣檢查
- `slitting_result`: 切割結果
- `additional_data`: 溫度、壓力等額外測量資料

### P3 - 追蹤編號
- `lot_no`: 批號
- `p3_no`: P3 追蹤編號
- `product_name`: 產品名稱
- `quantity`: 數量  
- `production_date`: 生產日期
- `notes`: 備註

## 預防措施

### 1. 遷移驗證流程
- 每次遷移後驗證實際資料庫結構
- 使用自動化腳本檢查模型與資料庫的一致性

### 2. 開發環境同步
- 建立標準的資料庫重置和遷移流程
- 文檔化所有手動資料庫變更

### 3. 錯誤監控
- 增強後端日誌記錄，特別是資料庫操作
- 實施資料庫結構健康檢查端點

## 測試建議

### 1. 立即測試
- 上傳 P1 類型檔案 (基本產品資料)
- 上傳 P2 類型檔案 (尺寸檢測資料) 
- 上傳 P3 類型檔案 (追蹤編號)
- 驗證批次匯入功能

### 2. 邊界測試
- 測試包含大量額外欄位的 CSV 檔案
- 驗證 JSONB additional_data 的正確存儲
- 測試 lot_no + data_type 的唯一約束

---
**修復狀態**: 完全解決
**測試狀態**: 待用戶驗證  
**修復時間**: 2025-11-16 16:45
**影響範圍**: 資料庫結構、檔案匯入功能、P1/P2/P3 資料類型支援