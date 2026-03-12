-- Backfill materialized fields in p2_items_v2 from row_data
-- Run in DB client after columns are added by migration 20260309_0003.

-- PostgreSQL
-- 1) Create helper to normalize common date strings (including 民國年 "114年08月27日" / "114年8月27日14:30")
CREATE OR REPLACE FUNCTION parse_p2_date_to_yyyymmdd(raw_text text)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    s text := NULLIF(trim(raw_text), '');
    v text;
BEGIN
    IF s IS NULL THEN
        RETURN NULL;
    END IF;

    -- 114年08月27日 / 114年8月27日14:30
    IF s ~ '^\d{3}年\d{1,2}月\d{1,2}日' THEN
        RETURN
            (regexp_replace(split_part(s, '年', 1), '\D', '', 'g')::int + 1911) * 10000 +
            lpad((regexp_replace(split_part(split_part(s, '年', 2), '月', 1), '\D', '', 'g'))::int::text, 2, '0')::int * 100 +
            lpad((regexp_replace(split_part(split_part(s, '月', 2), '日', 1), '\D', '', 'g'))::int::text, 2, '0')::int;
    END IF;

    -- 2025-08-27, 2025/08/27
    IF s ~ '^\d{4}[-/]\d{1,2}[-/]\d{1,2}$' THEN
        RETURN to_char(to_date(s, 'YYYY-MM-DD'), 'YYYYMMDD')::int;
    END IF;

    -- 20250827
    IF s ~ '^\d{8}$' THEN
        RETURN s::int;
    END IF;

    -- 1140902
    IF s ~ '^\d{7}$' THEN
        RETURN (substring(s,1,3)::int + 1911) * 10000
            + (substring(s,4,2)::int) * 100
            + (substring(s,6,2)::int);
    END IF;

    -- 250927 (fallback: assume ROC year)
    IF s ~ '^\d{6}$' THEN
        RETURN (substring(s,1,2)::int + 1911) * 10000
            + (substring(s,3,2)::int) * 100
            + (substring(s,5,2)::int);
    END IF;

    -- remove all non-digits fallback
    v := regexp_replace(s, '\D', '', 'g');
    IF v ~ '^\d{8}$' THEN
        RETURN v::int;
    END IF;
    IF v ~ '^\d{7}$' THEN
        RETURN (substring(v,1,3)::int + 1911) * 10000
            + (substring(v,4,2)::int) * 100
            + (substring(v,6,2)::int);
    END IF;
    IF v ~ '^\d{6}$' THEN
        RETURN (substring(v,1,2)::int + 1911) * 10000
            + (substring(v,3,2)::int) * 100
            + (substring(v,5,2)::int);
    END IF;
    RETURN NULL;
END
$$;

UPDATE p2_items_v2
SET
    production_date_yyyymmdd = COALESCE(
        production_date_yyyymmdd,
        parse_p2_date_to_yyyymmdd(COALESCE(
            NULLIF(row_data->>'Slitting date', ''),
            NULLIF(row_data->>'Slitting Date', ''),
            NULLIF(row_data->>'slitting date', ''),
            NULLIF(row_data->>'slitting_date', ''),
            NULLIF(row_data->>'Slitting Time', ''),
            NULLIF(row_data->>'slitting_time', ''),
            NULLIF(row_data->>'分條時間', ''),
            NULLIF(row_data->>'production_date', ''),
            NULLIF(row_data->>'Production Date', ''),
            NULLIF(row_data->>'生產日期', ''),
            NULLIF(row_data->>'date', ''),
            NULLIF(row_data->>'Date', ''),
            NULLIF(row_data->'rows'->0->>'Slitting date', ''),
            NULLIF(row_data->'rows'->0->>'Slitting Date', ''),
            NULLIF(row_data->'rows'->0->>'slitting date', ''),
            NULLIF(row_data->'rows'->0->>'slitting_date', ''),
            NULLIF(row_data->'rows'->0->>'Slitting Time', ''),
            NULLIF(row_data->'rows'->0->>'slitting_time', ''),
            NULLIF(row_data->'rows'->0->>'分條時間', ''),
            NULLIF(row_data->'rows'->0->>'production_date', ''),
            NULLIF(row_data->'rows'->0->>'Production Date', ''),
            NULLIF(row_data->'rows'->0->>'生產日期', ''),
            NULLIF(row_data->'rows'->0->>'date', ''),
            NULLIF(row_data->'rows'->0->>'Date', '')
        ))
    ),
    slitting_result = COALESCE(
        slitting_result,
        NULLIF(
            CAST(
                NULLIF(
                    COALESCE(
                        NULLIF(row_data->>'Striped Results', ''),
                        NULLIF(row_data->>'Striped results', ''),
                        NULLIF(row_data->>'striped results', ''),
                        NULLIF(row_data->>'striped result', ''),
                        NULLIF(row_data->>'Slitting Result', ''),
                        NULLIF(row_data->>'slitting result', ''),
                        NULLIF(row_data->>'slitting_result', ''),
                        NULLIF(row_data->>'分條結果', ''),
                        NULLIF(row_data->>'分條結果(成品)', ''),
                        NULLIF(row_data->'rows'->0->>'Striped Results', ''),
                        NULLIF(row_data->'rows'->0->>'Striped results', ''),
                        NULLIF(row_data->'rows'->0->>'striped results', ''),
                        NULLIF(row_data->'rows'->0->>'striped result', ''),
                        NULLIF(row_data->'rows'->0->>'Slitting Result', ''),
                        NULLIF(row_data->'rows'->0->>'slitting result', ''),
                        NULLIF(row_data->'rows'->0->>'slitting_result', ''),
                        NULLIF(row_data->'rows'->0->>'分條結果', ''),
                        NULLIF(row_data->'rows'->0->>'分條結果(成品)', '')
                    ),
                    ''
                )::numeric
            AS integer),
            NULL
        )
    )
WHERE
    production_date_yyyymmdd IS NULL OR slitting_result IS NULL;

DROP FUNCTION IF EXISTS parse_p2_date_to_yyyymmdd(text);


-- SQLite
-- SQLite cannot reliably parse 民國年份字串，建議先補齊含「YYYY/MM/DD」「YYYY-MM-DD」「YYYYMMDD」與 7 碼 ROC 格式。
UPDATE p2_items_v2
SET
    production_date_yyyymmdd = COALESCE(
        production_date_yyyymmdd,
        CASE
            WHEN TRIM(json_extract(row_data, '$.Slitting date')) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN CAST(TRIM(json_extract(row_data, '$.Slitting date')) AS INTEGER)
            WHEN TRIM(json_extract(row_data, '$.Slitting Date')) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN CAST(TRIM(json_extract(row_data, '$.Slitting Date')) AS INTEGER)
            WHEN TRIM(json_extract(row_data, '$.slitting date')) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN CAST(TRIM(json_extract(row_data, '$.slitting date')) AS INTEGER)
            WHEN TRIM(json_extract(row_data, '$.slitting_date')) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN CAST(TRIM(json_extract(row_data, '$.slitting_date')) AS INTEGER)
            WHEN TRIM(json_extract(row_data, '$.Slitting Time')) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN CAST(TRIM(json_extract(row_data, '$.Slitting Time')) AS INTEGER)
            WHEN TRIM(json_extract(row_data, '$.分條時間')) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN CAST(TRIM(json_extract(row_data, '$.分條時間')) AS INTEGER)
            WHEN TRIM(json_extract(row_data, '$.production_date')) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN CAST(TRIM(json_extract(row_data, '$.production_date')) AS INTEGER)
            ELSE NULL
        END,
        NULL
    ),
    slitting_result = COALESCE(
        slitting_result,
        CAST(
            NULLIF(
                TRIM(COALESCE(
                    NULLIF(json_extract(row_data, '$.Striped Results'), ''),
                    NULLIF(json_extract(row_data, '$.Striped results'), ''),
                    NULLIF(json_extract(row_data, '$.striped results'), ''),
                    NULLIF(json_extract(row_data, '$.striped result'), ''),
                    NULLIF(json_extract(row_data, '$.Slitting Result'), ''),
                    NULLIF(json_extract(row_data, '$.slitting result'), ''),
                    NULLIF(json_extract(row_data, '$.slitting_result'), ''),
                    NULLIF(json_extract(row_data, '$.分條結果'), ''),
                    NULLIF(json_extract(row_data, '$.分條結果(成品)'), '')
                )),
                ''
            ) AS INTEGER
        )
    )
WHERE
    production_date_yyyymmdd IS NULL OR slitting_result IS NULL;
