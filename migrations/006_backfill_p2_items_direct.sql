-- =====================================================
-- P2 Items Backfill (Direct from JSON)
-- =====================================================
-- Purpose: Safely populate p2_items table from existing records' additional_data
--          without modifying or deleting the original records.
--          This is a safer alternative to running 004 + 005.
-- =====================================================

-- 1. Ensure p2_items table exists
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

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS ix_p2_items_record_id ON p2_items(record_id);
CREATE INDEX IF NOT EXISTS ix_p2_items_record_winder ON p2_items(record_id, winder_number);
-- Note: We skip the UNIQUE index for now to avoid blocking backfill if duplicates exist in JSON, 
-- but ideally it should be there.
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_p2_items_record_winder ON p2_items(record_id, winder_number);

DO $$
DECLARE
    r RECORD;
    row_data jsonb;
    row_index int;
    winder_val int;
    inserted_count int := 0;
BEGIN
    RAISE NOTICE 'Starting P2 items backfill...';

    -- Iterate through all P2 records that have rows data
    FOR r IN 
        SELECT id, lot_no, additional_data 
        FROM records 
        WHERE data_type = 'P2' 
          AND additional_data ? 'rows' 
          AND jsonb_array_length(additional_data->'rows') > 0
    LOOP
        row_index := 0;
        
        -- Iterate through each row in the JSON array
        FOR row_data IN SELECT * FROM jsonb_array_elements(r.additional_data->'rows')
        LOOP
            row_index := row_index + 1;
            
            -- Try to extract winder number from JSON, fallback to index
            -- Keys checked: 'Winder number', 'winder number', 'Winder', 'winder', '收卷機', '收卷機編號', '捲收機號碼'
            winder_val := NULL;
            
            IF row_data ? 'Winder number' THEN winder_val := (row_data->>'Winder number')::int;
            ELSIF row_data ? 'winder number' THEN winder_val := (row_data->>'winder number')::int;
            ELSIF row_data ? 'Winder' THEN winder_val := (row_data->>'Winder')::int;
            ELSIF row_data ? 'winder' THEN winder_val := (row_data->>'winder')::int;
            ELSIF row_data ? '收卷機' THEN winder_val := (row_data->>'收卷機')::int;
            ELSIF row_data ? '收卷機編號' THEN winder_val := (row_data->>'收卷機編號')::int;
            ELSIF row_data ? '捲收機號碼' THEN winder_val := (row_data->>'捲收機號碼')::int;
            END IF;
            
            IF winder_val IS NULL THEN
                winder_val := row_index;
            END IF;

            -- Insert into p2_items if not exists
            IF NOT EXISTS (
                SELECT 1 FROM p2_items 
                WHERE record_id = r.id AND winder_number = winder_val
            ) THEN
                INSERT INTO p2_items (
                    record_id,
                    winder_number,
                    sheet_width,
                    thickness1, thickness2, thickness3, thickness4, thickness5, thickness6, thickness7,
                    appearance,
                    rough_edge,
                    slitting_result,
                    row_data
                ) VALUES (
                    r.id,
                    winder_val,
                    (row_data->>'Sheet Width(mm)')::float,
                    (row_data->>'Thicknessss1(μm)')::float,
                    (row_data->>'Thicknessss2(μm)')::float,
                    (row_data->>'Thicknessss3(μm)')::float,
                    (row_data->>'Thicknessss4(μm)')::float,
                    (row_data->>'Thicknessss5(μm)')::float,
                    (row_data->>'Thicknessss6(μm)')::float,
                    (row_data->>'Thicknessss7(μm)')::float,
                    CASE 
                        WHEN (row_data->>'Appearance') = 'OK' THEN 1
                        WHEN (row_data->>'Appearance') = 'NG' THEN 0
                        WHEN (row_data->>'Appearance') ~ '^[0-9\.]+$' THEN (row_data->>'Appearance')::numeric::int
                        ELSE NULL
                    END,
                    CASE 
                        WHEN (row_data->>'rough edge') = 'OK' THEN 1
                        WHEN (row_data->>'rough edge') = 'NG' THEN 0
                        WHEN (row_data->>'rough edge') ~ '^[0-9\.]+$' THEN (row_data->>'rough edge')::numeric::int
                        ELSE NULL
                    END,
                    CASE 
                        WHEN (row_data->>'Slitting Result') = 'OK' THEN 1
                        WHEN (row_data->>'Slitting Result') = 'NG' THEN 0
                        WHEN (row_data->>'Slitting Result') ~ '^[0-9\.]+$' THEN (row_data->>'Slitting Result')::numeric::int
                        ELSE NULL
                    END,
                    row_data
                );
                inserted_count := inserted_count + 1;
            END IF;
        END LOOP;
    END LOOP;

    RAISE NOTICE 'P2 items backfill completed. Inserted % items.', inserted_count;
END $$;
