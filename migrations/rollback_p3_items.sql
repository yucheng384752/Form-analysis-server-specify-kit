-- ============================================================
-- P3 Items 回滾腳本
-- ============================================================
-- 版本: 1.0
-- 日期: 2025-01-22
-- 說明: 如果需要回滾 P3 Items 遷移，執行此腳本
-- 警告: 這將刪除 p3_items 表及所有資料
-- ============================================================

BEGIN;

-- ============================================================
-- Step 1: 確認回滾操作
-- ============================================================

DO $$
BEGIN
    RAISE WARNING '
    ============================================================
     警告：即將回滾 P3 Items 遷移
    ============================================================
    
    這將執行以下操作:
    1. 刪除 p3_items 表
    2. 刪除所有相關索引
    3. 刪除所有觸發器
    4. 永久刪除所有 P3 明細資料
    
    如果要繼續，請執行此腳本
    如果要取消，請按 Ctrl+C
    
    等待 5 秒後開始...
    ============================================================
    ';
    
    -- PostgreSQL 不支援 WAITFOR，這只是提示
    -- 實際使用時建議手動確認
END $$;

-- ============================================================
-- Step 2: 備份現有資料（可選）
-- ============================================================

-- 如果需要備份，先創建備份表
-- CREATE TABLE p3_items_backup AS SELECT * FROM p3_items;
-- RAISE NOTICE 'Backup created: p3_items_backup';

-- ============================================================
-- Step 3: 刪除觸發器
-- ============================================================

DO $$
BEGIN
    -- 刪除 updated_at 觸發器
    IF EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'update_p3_items_updated_at'
    ) THEN
        DROP TRIGGER update_p3_items_updated_at ON p3_items;
        RAISE NOTICE 'Trigger update_p3_items_updated_at dropped';
    END IF;
END $$;

-- ============================================================
-- Step 4: 刪除索引（表刪除時會自動刪除，此處列出供參考）
-- ============================================================

/*
-- 這些索引會在表刪除時自動刪除
DROP INDEX IF EXISTS ix_p3_items_record_id;
DROP INDEX IF EXISTS ix_p3_items_product_id;
DROP INDEX IF EXISTS ix_p3_items_lot_no;
DROP INDEX IF EXISTS ix_p3_items_production_date;
DROP INDEX IF EXISTS ix_p3_items_machine_no;
DROP INDEX IF EXISTS ix_p3_items_mold_no;
DROP INDEX IF EXISTS ix_p3_items_specification;
DROP INDEX IF EXISTS ix_p3_items_bottom_tape_lot;
DROP INDEX IF EXISTS ix_p3_items_source_winder;
DROP INDEX IF EXISTS ix_p3_items_record_id_row_no;
DROP INDEX IF EXISTS ix_p3_items_lot_no_row_no;
DROP INDEX IF EXISTS ix_p3_items_machine_no_mold_no;
*/

-- ============================================================
-- Step 5: 刪除 p3_items 表
-- ============================================================

DO $$
DECLARE
    item_count INTEGER;
BEGIN
    -- 記錄要刪除的資料數量
    SELECT COUNT(*) INTO item_count FROM p3_items;
    
    RAISE NOTICE 'Dropping p3_items table with % rows', item_count;
    
    -- 刪除表（CASCADE 會自動刪除相關約束）
    DROP TABLE IF EXISTS p3_items CASCADE;
    
    RAISE NOTICE ' Table p3_items dropped successfully';
END $$;

-- ============================================================
-- Step 6: 驗證回滾結果
-- ============================================================

DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'p3_items'
    ) INTO table_exists;
    
    IF table_exists THEN
        RAISE EXCEPTION 'Table p3_items still exists after rollback';
    ELSE
        RAISE NOTICE ' Rollback verification passed: p3_items table removed';
    END IF;
END $$;

-- ============================================================
-- Step 7: 清理觸發器函數（可選）
-- ============================================================

-- 如果不再需要 update_updated_at_column 函數
-- 注意：如果其他表也使用此函數，不要刪除
/*
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
RAISE NOTICE 'Function update_updated_at_column dropped';
*/

COMMIT;

-- ============================================================
-- 回滾完成提示
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '
    ============================================================
     P3 Items 回滾完成
    ============================================================
    
    已刪除:
    - p3_items 表
    - 所有索引
    - 所有約束
    - 所有觸發器
    - 所有資料
    
    下一步:
    1. 如果需要，還原備份資料
    2. 如果要重新遷移，執行 001_create_p3_items.sql
    
    ============================================================
    ';
END $$;
