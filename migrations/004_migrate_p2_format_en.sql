-- P2 Data Format Migration
-- Convert from merged format to row-by-row format

DO $$
DECLARE
    p2_record RECORD;
    row_data jsonb;
    row_index int;
    total_migrated int := 0;
    total_rows_expanded int := 0;
BEGIN
    RAISE NOTICE 'Starting P2 data format migration...';
    
    -- Process all P2 records with old format
    FOR p2_record IN 
        SELECT id, lot_no, production_date, additional_data, created_at
        FROM records
        WHERE data_type = 'P2'
          AND winder_number IS NULL
          AND additional_data ? 'rows'
          AND jsonb_array_length(additional_data->'rows') > 0
    LOOP
        RAISE NOTICE 'Processing P2 record: lot_no=%, rows=%', 
                     p2_record.lot_no, 
                     jsonb_array_length(p2_record.additional_data->'rows');
        
        -- Iterate through each row in additional_data->rows array
        row_index := 1;
        FOR row_data IN 
            SELECT * FROM jsonb_array_elements(p2_record.additional_data->'rows')
        LOOP
            -- Check if record already exists
            IF NOT EXISTS (
                SELECT 1 FROM records
                WHERE lot_no = p2_record.lot_no
                  AND data_type = 'P2'
                  AND winder_number = row_index
            ) THEN
                -- Insert new row record
                INSERT INTO records (
                    id,
                    lot_no,
                    data_type,
                    winder_number,
                    production_date,
                    additional_data,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    p2_record.lot_no,
                    'P2',
                    row_index,
                    p2_record.production_date,
                    row_data,
                    p2_record.created_at
                );
                
                total_rows_expanded := total_rows_expanded + 1;
            END IF;
            
            row_index := row_index + 1;
        END LOOP;
        
        -- Delete old merged record
        DELETE FROM records WHERE id = p2_record.id;
        total_migrated := total_migrated + 1;
        
        RAISE NOTICE '  Migration completed: lot_no=%, expanded % records', 
                     p2_record.lot_no, 
                     row_index - 1;
    END LOOP;
    
    RAISE NOTICE 'P2 data format migration completed!';
    RAISE NOTICE '  Migrated P2 records: %', total_migrated;
    RAISE NOTICE '  Expanded rows: %', total_rows_expanded;
    
    -- Verify migration results
    RAISE NOTICE 'Migration verification:';
    RAISE NOTICE '  Total P2 records: %', (SELECT COUNT(*) FROM records WHERE data_type = 'P2');
    RAISE NOTICE '  Records with winder_number: %', (SELECT COUNT(*) FROM records WHERE data_type = 'P2' AND winder_number IS NOT NULL);
    RAISE NOTICE '  Old format records (should be 0): %', (SELECT COUNT(*) FROM records WHERE data_type = 'P2' AND winder_number IS NULL AND additional_data ? 'rows');
    
END $$;

-- Show sample of migrated data
SELECT 
    lot_no,
    winder_number,
    production_date,
    created_at
FROM records
WHERE data_type = 'P2'
ORDER BY lot_no, winder_number
LIMIT 20;
