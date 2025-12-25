-- ============================================================
-- P3 Items 資料回填腳本（可選）
-- ============================================================
-- 版本: 1.0
-- 日期: 2025-01-22
-- 說明: 將現有 records 表中的 P3 資料回填到 p3_items 表
-- 警告: 僅在資料庫中已有 P3 資料時執行
-- ============================================================

BEGIN;

-- ============================================================
-- Step 1: 檢查是否有需要回填的 P3 資料
-- ============================================================

DO $$
DECLARE
    p3_record_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO p3_record_count
    FROM records
    WHERE data_type = 'P3' 
    AND additional_data IS NOT NULL
    AND additional_data::text LIKE '%rows%';
    
    RAISE NOTICE 'Found % P3 records to backfill', p3_record_count;
    
    IF p3_record_count = 0 THEN
        RAISE NOTICE 'No P3 records found, skipping backfill';
    END IF;
END $$;

-- ============================================================
-- Step 2: 回填資料
-- ============================================================

-- 注意：這個 SQL 需要根據實際的 additional_data 結構調整
-- 假設 additional_data 格式為: {"rows": [{...}, {...}]}

INSERT INTO p3_items (
    record_id,
    row_no,
    lot_no,
    production_date,
    machine_no,
    mold_no,
    specification,
    bottom_tape_lot,
    row_data,
    created_at
)
SELECT 
    r.id AS record_id,
    (row_number() OVER (PARTITION BY r.id ORDER BY r.created_at))::INTEGER AS row_no,
    r.lot_no,
    r.production_date,
    -- 從第一列提取機台編號（如果存在）
    (r.additional_data->'rows'->0->>'Machine NO')::VARCHAR(20) AS machine_no,
    -- 從第一列提取模具編號（如果存在）
    (r.additional_data->'rows'->0->>'Mold NO')::VARCHAR(50) AS mold_no,
    -- 從第一列提取規格（如果存在）
    (r.additional_data->'rows'->0->>'Specification')::VARCHAR(100) AS specification,
    -- 從第一列提取下膠編號（如果存在）
    (r.additional_data->'rows'->0->>'Bottom Tape')::VARCHAR(50) AS bottom_tape_lot,
    -- 完整的行資料
    row_item.value AS row_data,
    r.created_at
FROM records r
CROSS JOIN LATERAL jsonb_array_elements(r.additional_data->'rows') WITH ORDINALITY AS row_item(value, row_num)
WHERE r.data_type = 'P3'
AND r.additional_data IS NOT NULL
AND r.additional_data ? 'rows'
-- 避免重複插入
AND NOT EXISTS (
    SELECT 1 FROM p3_items pi WHERE pi.record_id = r.id
);

-- ============================================================
-- Step 3: 更新 product_id（如果可以生成）
-- ============================================================

-- 根據現有資料生成 product_id
-- 格式: YYYYMMDD_machine_mold_lot

UPDATE p3_items
SET product_id = CONCAT(
    TO_CHAR(production_date, 'YYYYMMDD'),
    '_',
    machine_no,
    '_',
    mold_no,
    '_',
    production_lot
)
WHERE product_id IS NULL
AND production_date IS NOT NULL
AND machine_no IS NOT NULL
AND mold_no IS NOT NULL
AND production_lot IS NOT NULL;

-- ============================================================
-- Step 4: 更新 source_winder（從 lot_no 提取）
-- ============================================================

UPDATE p3_items
SET source_winder = CASE
    WHEN LENGTH(lot_no) >= 2 
    AND RIGHT(lot_no, 2) ~ '^\d+$'  -- 檢查是否為數字
    THEN RIGHT(lot_no, 2)::INTEGER
    ELSE NULL
END
WHERE source_winder IS NULL;

-- ============================================================
-- Step 5: 驗證回填結果
-- ============================================================

DO $$
DECLARE
    backfilled_count INTEGER;
    record_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO backfilled_count FROM p3_items;
    SELECT COUNT(*) INTO record_count FROM records WHERE data_type = 'P3';
    
    RAISE NOTICE 'Backfill complete:';
    RAISE NOTICE '- P3 records: %', record_count;
    RAISE NOTICE '- P3 items created: %', backfilled_count;
    
    IF backfilled_count = 0 AND record_count > 0 THEN
        RAISE WARNING 'No items were backfilled, check additional_data structure';
    END IF;
END $$;

-- ============================================================
-- Step 6: 顯示回填資料摘要
-- ============================================================

SELECT 
    r.lot_no,
    r.data_type,
    COUNT(pi.id) AS item_count,
    MIN(pi.row_no) AS first_row,
    MAX(pi.row_no) AS last_row
FROM records r
LEFT JOIN p3_items pi ON pi.record_id = r.id
WHERE r.data_type = 'P3'
GROUP BY r.id, r.lot_no, r.data_type
ORDER BY r.created_at DESC
LIMIT 10;

COMMIT;

-- ============================================================
-- 回填完成提示
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '
    ============================================================
     P3 Items 資料回填完成
    ============================================================
    
    執行內容:
    - 從 records.additional_data 提取 P3 資料
    - 為每一列創建 p3_items 記錄
    - 生成 product_id（如果欄位齊全）
    - 提取 source_winder（從 lot_no）
    
    注意:
    - 如果 additional_data 結構不同，需要調整 SQL
    - 建議先在測試環境執行
    
    ============================================================
    ';
END $$;
