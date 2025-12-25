-- ============================================================
-- P3 Items 子表資料庫遷移腳本
-- ============================================================
-- 版本: 1.0
-- 日期: 2025-01-22
-- 說明: 創建 p3_items 表及相關索引、約束、觸發器
-- ============================================================

-- ============================================================
-- Step 1: 創建 p3_items 表
-- ============================================================

BEGIN;

-- 檢查表是否已存在
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'p3_items') THEN
        RAISE NOTICE 'Table p3_items already exists, skipping creation';
    ELSE
        CREATE TABLE p3_items (
            -- 主鍵
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            
            -- 外鍵：關聯到 records 表
            record_id UUID NOT NULL,
            
            -- 列序號（在 CSV 檔案中的順序）
            row_no INTEGER NOT NULL,
            
            -- 產品編號（業務唯一鍵，用於追溯）
            product_id VARCHAR(100) UNIQUE,
            
            -- 批號（繼承自父表，方便直接查詢）
            lot_no VARCHAR(50) NOT NULL,
            
            -- 生產日期
            production_date DATE,
            
            -- 機台編號
            machine_no VARCHAR(20),
            
            -- 模具編號
            mold_no VARCHAR(50),
            
            -- 生產序號/批次號
            production_lot INTEGER,
            
            -- 來源收卷機編號（用於追溯 P2）
            source_winder INTEGER,
            
            -- 規格
            specification VARCHAR(100),
            
            -- 下膠編號/Bottom Tape LOT
            bottom_tape_lot VARCHAR(50),
            
            -- 該列的完整原始資料（JSONB）
            row_data JSONB,
            
            -- 時間戳欄位
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            
            -- 外鍵約束
            CONSTRAINT fk_p3_items_record_id 
                FOREIGN KEY (record_id) 
                REFERENCES records(id) 
                ON DELETE CASCADE
        );
        
        RAISE NOTICE 'Table p3_items created successfully';
    END IF;
END $$;

COMMIT;

-- ============================================================
-- Step 2: 創建索引
-- ============================================================

BEGIN;

-- 2.1 外鍵索引（record_id）
CREATE INDEX IF NOT EXISTS ix_p3_items_record_id 
ON p3_items(record_id);

-- 2.2 產品編號索引（唯一性已在欄位定義中）
CREATE INDEX IF NOT EXISTS ix_p3_items_product_id 
ON p3_items(product_id);

-- 2.3 批號索引
CREATE INDEX IF NOT EXISTS ix_p3_items_lot_no 
ON p3_items(lot_no);

-- 2.4 生產日期索引
CREATE INDEX IF NOT EXISTS ix_p3_items_production_date 
ON p3_items(production_date);

-- 2.5 機台編號索引
CREATE INDEX IF NOT EXISTS ix_p3_items_machine_no 
ON p3_items(machine_no);

-- 2.6 模具編號索引
CREATE INDEX IF NOT EXISTS ix_p3_items_mold_no 
ON p3_items(mold_no);

-- 2.7 規格索引
CREATE INDEX IF NOT EXISTS ix_p3_items_specification 
ON p3_items(specification);

-- 2.8 下膠編號索引
CREATE INDEX IF NOT EXISTS ix_p3_items_bottom_tape_lot 
ON p3_items(bottom_tape_lot);

-- 2.9 來源收卷機索引
CREATE INDEX IF NOT EXISTS ix_p3_items_source_winder 
ON p3_items(source_winder);

-- 2.10 複合索引：record_id + row_no（用於排序）
CREATE INDEX IF NOT EXISTS ix_p3_items_record_id_row_no 
ON p3_items(record_id, row_no);

-- 2.11 複合索引：lot_no + row_no（用於批號內排序）
CREATE INDEX IF NOT EXISTS ix_p3_items_lot_no_row_no 
ON p3_items(lot_no, row_no);

-- 2.12 複合索引：machine_no + mold_no（用於機台模具組合查詢）
CREATE INDEX IF NOT EXISTS ix_p3_items_machine_no_mold_no 
ON p3_items(machine_no, mold_no);

RAISE NOTICE 'All indexes created successfully';

COMMIT;

-- ============================================================
-- Step 3: 創建 updated_at 自動更新觸發器
-- ============================================================

BEGIN;

-- 3.1 創建觸發器函數（如果不存在）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3.2 創建觸發器
DROP TRIGGER IF EXISTS update_p3_items_updated_at ON p3_items;

CREATE TRIGGER update_p3_items_updated_at
    BEFORE UPDATE ON p3_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

RAISE NOTICE 'Trigger update_p3_items_updated_at created successfully';

COMMIT;

-- ============================================================
-- Step 4: 驗證表結構
-- ============================================================

DO $$
DECLARE
    table_count INTEGER;
    index_count INTEGER;
    fk_count INTEGER;
BEGIN
    -- 檢查表是否存在
    SELECT COUNT(*) INTO table_count
    FROM pg_tables
    WHERE schemaname = 'public' AND tablename = 'p3_items';
    
    IF table_count = 0 THEN
        RAISE EXCEPTION 'Table p3_items was not created successfully';
    END IF;
    
    -- 檢查索引數量
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'public' AND tablename = 'p3_items';
    
    RAISE NOTICE 'Verification: Found % indexes on p3_items', index_count;
    
    -- 檢查外鍵約束
    SELECT COUNT(*) INTO fk_count
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
    AND table_name = 'p3_items';
    
    RAISE NOTICE 'Verification: Found % foreign keys on p3_items', fk_count;
    
    RAISE NOTICE ' Table structure verification passed';
END $$;

-- ============================================================
-- Step 5: 顯示表結構資訊
-- ============================================================

-- 5.1 列出所有欄位
SELECT 
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'p3_items'
ORDER BY ordinal_position;

-- 5.2 列出所有索引
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'p3_items'
ORDER BY indexname;

-- 5.3 列出所有約束
SELECT 
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'p3_items'
ORDER BY constraint_type, constraint_name;

-- ============================================================
-- 遷移完成提示
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '
    ============================================================
     P3 Items 資料庫遷移完成
    ============================================================
    
    已創建:
    - p3_items 表（15 個欄位）
    - 12 個索引（單獨 + 複合）
    - 1 個外鍵約束（CASCADE DELETE）
    - 1 個 UNIQUE 約束（product_id）
    - 1 個 updated_at 觸發器
    
    下一步:
    1. 驗證應用程式連接
    2. 測試 P3 檔案匯入功能
    3. 檢查日誌輸出
    
    ============================================================
    ';
END $$;
