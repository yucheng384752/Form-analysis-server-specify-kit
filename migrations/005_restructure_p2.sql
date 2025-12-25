-- =====================================================
-- P2 資料結構重構：從逐行記錄轉為父子表結構
-- =====================================================
-- 目的：將 P2 資料結構改為與 P3 一致
--      1. 父表 records：每個檔案/批號一筆記錄
--      2. 子表 p2_items：每個卷收機一筆明細
--
-- 步驟：
-- 1. 創建 p2_items 表
-- 2. 遷移現有資料
-- 3. 清理舊資料
-- =====================================================

-- 1. 創建 p2_items 表
CREATE TABLE IF NOT EXISTS p2_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    winder_number INTEGER NOT NULL,
    sheet_width DOUBLE PRECISION,
    thickness1 DOUBLE PRECISION,
    thickness2 DOUBLE PRECISION,
    thickness3 DOUBLE PRECISION,
    thickness4 DOUBLE PRECISION,
    thickness5 DOUBLE PRECISION,
    thickness6 DOUBLE PRECISION,
    thickness7 DOUBLE PRECISION,
    appearance INTEGER,
    rough_edge INTEGER,
    slitting_result INTEGER,
    row_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 建立索引
CREATE INDEX IF NOT EXISTS ix_p2_items_record_id ON p2_items(record_id);
CREATE INDEX IF NOT EXISTS ix_p2_items_record_winder ON p2_items(record_id, winder_number);
CREATE UNIQUE INDEX IF NOT EXISTS uq_p2_items_record_winder ON p2_items(record_id, winder_number);

-- 2. 資料遷移
DO $$
DECLARE
    lot_record RECORD;
    p2_row RECORD;
    new_record_id UUID;
    migrated_count INT := 0;
    items_count INT := 0;
BEGIN
    RAISE NOTICE 'Starting P2 data structure restructuring...';
    
    -- Find all P2 lots (grouped)
    FOR lot_record IN 
        SELECT DISTINCT lot_no, production_date 
        FROM records 
        WHERE data_type = 'P2' AND winder_number IS NOT NULL
    LOOP
        RAISE NOTICE 'Processing lot: %', lot_record.lot_no;
        
        -- 1. Create new parent record (Header)
        INSERT INTO records (
            id, lot_no, data_type, production_date, created_at, winder_number
        ) VALUES (
            gen_random_uuid(),
            lot_record.lot_no,
            'P2',
            lot_record.production_date,
            NOW(),
            NULL -- Header 的 winder_number 為 NULL
        ) RETURNING id INTO new_record_id;
        
        -- 2. 將現有的逐行記錄遷移到 p2_items
        FOR p2_row IN 
            SELECT * FROM records 
            WHERE data_type = 'P2' 
              AND lot_no = lot_record.lot_no 
              AND winder_number IS NOT NULL
            ORDER BY winder_number
        LOOP
            INSERT INTO p2_items (
                record_id,
                winder_number,
                sheet_width,
                thickness1, thickness2, thickness3, thickness4, thickness5, thickness6, thickness7,
                appearance, rough_edge, slitting_result,
                row_data
            ) VALUES (
                new_record_id,
                p2_row.winder_number,
                (p2_row.additional_data->>'Sheet Width(mm)')::float,
                (p2_row.additional_data->>'Thicknessss1(μm)')::float,
                (p2_row.additional_data->>'Thicknessss2(μm)')::float,
                (p2_row.additional_data->>'Thicknessss3(μm)')::float,
                (p2_row.additional_data->>'Thicknessss4(μm)')::float,
                (p2_row.additional_data->>'Thicknessss5(μm)')::float,
                (p2_row.additional_data->>'Thicknessss6(μm)')::float,
                (p2_row.additional_data->>'Thicknessss7(μm)')::float,
                CASE 
                    WHEN (p2_row.additional_data->>'Appearance') = 'OK' THEN 1
                    WHEN (p2_row.additional_data->>'Appearance') = 'NG' THEN 0
                    WHEN (p2_row.additional_data->>'Appearance') ~ '^[0-9\.]+$' THEN (p2_row.additional_data->>'Appearance')::numeric::int
                    ELSE NULL
                END,
                CASE 
                    WHEN (p2_row.additional_data->>'rough edge') = 'OK' THEN 1
                    WHEN (p2_row.additional_data->>'rough edge') = 'NG' THEN 0
                    WHEN (p2_row.additional_data->>'rough edge') ~ '^[0-9\.]+$' THEN (p2_row.additional_data->>'rough edge')::numeric::int
                    ELSE NULL
                END,
                CASE 
                    WHEN (p2_row.additional_data->>'Slitting Result') = 'OK' THEN 1
                    WHEN (p2_row.additional_data->>'Slitting Result') = 'NG' THEN 0
                    WHEN (p2_row.additional_data->>'Slitting Result') ~ '^[0-9\.]+$' THEN (p2_row.additional_data->>'Slitting Result')::numeric::int
                    ELSE NULL
                END,
                p2_row.additional_data
            );
            items_count := items_count + 1;
        END LOOP;
        
        -- 3. 刪除舊的逐行記錄
        DELETE FROM records 
        WHERE data_type = 'P2' 
          AND lot_no = lot_record.lot_no 
          AND winder_number IS NOT NULL;
          
        migrated_count := migrated_count + 1;
    END LOOP;
    
    RAISE NOTICE 'Migration completed!';
    RAISE NOTICE '  Migrated lots: %', migrated_count;
    RAISE NOTICE '  Created items: %', items_count;
    
END $$;

-- 驗證結果
SELECT r.lot_no, COUNT(i.id) as item_count
FROM records r
JOIN p2_items i ON r.id = i.record_id
WHERE r.data_type = 'P2'
GROUP BY r.lot_no;
