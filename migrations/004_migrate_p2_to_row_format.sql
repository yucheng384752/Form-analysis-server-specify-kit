-- =====================================================
-- P2 資料格式遷移
-- =====================================================
-- 目的：將 P2 從合併格式（所有 rows 在 additional_data）
--      轉換為逐行格式（每個 winder 一筆 record）
--
-- 遷移前：
--   1 筆 P2 record (lot_no='2503033_01')
--   additional_data->rows: [row1, row2, ..., row20]
--   winder_number: NULL
--
-- 遷移後：
--   20 筆 P2 records (lot_no='2503033_01')
--   record 1: winder_number=1, additional_data=row1
--   record 2: winder_number=2, additional_data=row2
--   ...
--   record 20: winder_number=20, additional_data=row20
-- =====================================================

DO $$
DECLARE
    p2_record RECORD;
    row_data jsonb;
    row_index int;
    total_migrated int := 0;
    total_rows_expanded int := 0;
BEGIN
    RAISE NOTICE '開始 P2 資料格式遷移...';
    
    -- 遍歷所有需要遷移的 P2 記錄（winder_number 為 NULL 且 additional_data 有 rows 陣列）
    FOR p2_record IN 
        SELECT id, lot_no, production_date, additional_data, created_at
        FROM records
        WHERE data_type = 'P2'
          AND winder_number IS NULL
          AND additional_data ? 'rows'
          AND jsonb_array_length(additional_data->'rows') > 0
    LOOP
        RAISE NOTICE '處理 P2 記錄: lot_no=%, rows=%', 
                     p2_record.lot_no, 
                     jsonb_array_length(p2_record.additional_data->'rows');
        
        -- 遍歷 additional_data->rows 陣列中的每個元素
        row_index := 1;
        FOR row_data IN 
            SELECT * FROM jsonb_array_elements(p2_record.additional_data->'rows')
        LOOP
            -- 檢查是否已存在相同 lot_no + winder_number 的記錄（避免重複）
            IF NOT EXISTS (
                SELECT 1 FROM records
                WHERE lot_no = p2_record.lot_no
                  AND data_type = 'P2'
                  AND winder_number = row_index
            ) THEN
                -- 插入新的單行記錄
                INSERT INTO records (
                    lot_no,
                    data_type,
                    winder_number,
                    production_date,
                    additional_data,
                    created_at,
                    updated_at
                ) VALUES (
                    p2_record.lot_no,
                    'P2',
                    row_index,
                    p2_record.production_date,
                    row_data,  -- 單個 row 的資料
                    p2_record.created_at,
                    NOW()
                );
                
                total_rows_expanded := total_rows_expanded + 1;
            END IF;
            
            row_index := row_index + 1;
        END LOOP;
        
        -- 刪除舊的合併記錄
        DELETE FROM records WHERE id = p2_record.id;
        total_migrated := total_migrated + 1;
        
        RAISE NOTICE '  遷移完成: lot_no=%, 展開 % 筆記錄', 
                     p2_record.lot_no, 
                     row_index - 1;
    END LOOP;
    
    RAISE NOTICE 'P2 資料格式遷移完成！';
    RAISE NOTICE '  遷移的 P2 記錄數：%', total_migrated;
    RAISE NOTICE '  展開的總行數：%', total_rows_expanded;
    
    -- 驗證遷移結果
    RAISE NOTICE '遷移後驗證：';
    RAISE NOTICE '  P2 記錄總數：%', (SELECT COUNT(*) FROM records WHERE data_type = 'P2');
    RAISE NOTICE '  有 winder_number 的記錄：%', (SELECT COUNT(*) FROM records WHERE data_type = 'P2' AND winder_number IS NOT NULL);
    RAISE NOTICE '  舊格式記錄（應為0）：%', (SELECT COUNT(*) FROM records WHERE data_type = 'P2' AND winder_number IS NULL AND additional_data ? 'rows');
    
END $$;

-- 顯示遷移後的資料樣本
SELECT 
    lot_no,
    winder_number,
    production_date,
    jsonb_object_keys(additional_data) as data_keys,
    created_at
FROM records
WHERE data_type = 'P2'
ORDER BY lot_no, winder_number
LIMIT 10;
