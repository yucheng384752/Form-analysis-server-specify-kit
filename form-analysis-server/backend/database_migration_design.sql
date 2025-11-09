-- 資料庫遷移設計 - 以 lot_no 為唯一鍵的生產數據管理系統
-- 設計日期: 2025-11-08

-- ========================================
-- 1. 生產批次主表 (Production Lots)
-- ========================================
CREATE TABLE IF NOT EXISTS production_lots (
    lot_no VARCHAR(20) PRIMARY KEY,  -- 唯一鍵: 格式 2503033_01
    production_date DATE NOT NULL,
    production_time_start TIME,
    production_time_end TIME,
    product_spec VARCHAR(100),       -- 品名規格 (如 0.32mm)
    material VARCHAR(50),            -- 材料 (如 H5)
    semi_product_width DECIMAL(10,2), -- 半成品板寬 (mm)
    semi_product_length DECIMAL(10,2), -- 半成品米數 (M)
    weight DECIMAL(10,2),            -- 重量 (Kg)
    good_products INTEGER DEFAULT 0,  -- 良品數
    defective_products INTEGER DEFAULT 0, -- 不良品數
    remarks TEXT,                    -- 備註
    phase VARCHAR(2) NOT NULL,       -- P1, P2, P3
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 2. P1階段 - 押出機生產條件
-- ========================================
CREATE TABLE IF NOT EXISTS p1_extrusion_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_no VARCHAR(20) NOT NULL REFERENCES production_lots(lot_no) ON DELETE CASCADE,
    
    -- 實際溫度 (16個控制點)
    actual_temp_c1 DECIMAL(5,1), actual_temp_c2 DECIMAL(5,1), 
    actual_temp_c3 DECIMAL(5,1), actual_temp_c4 DECIMAL(5,1),
    actual_temp_c5 DECIMAL(5,1), actual_temp_c6 DECIMAL(5,1),
    actual_temp_c7 DECIMAL(5,1), actual_temp_c8 DECIMAL(5,1),
    actual_temp_c9 DECIMAL(5,1), actual_temp_c10 DECIMAL(5,1),
    actual_temp_c11 DECIMAL(5,1), actual_temp_c12 DECIMAL(5,1),
    actual_temp_c13 DECIMAL(5,1), actual_temp_c14 DECIMAL(5,1),
    actual_temp_c15 DECIMAL(5,1), actual_temp_c16 DECIMAL(5,1),
    
    -- 設定溫度 (16個控制點)
    set_temp_c1 DECIMAL(5,1), set_temp_c2 DECIMAL(5,1),
    set_temp_c3 DECIMAL(5,1), set_temp_c4 DECIMAL(5,1),
    set_temp_c5 DECIMAL(5,1), set_temp_c6 DECIMAL(5,1),
    set_temp_c7 DECIMAL(5,1), set_temp_c8 DECIMAL(5,1),
    set_temp_c9 DECIMAL(5,1), set_temp_c10 DECIMAL(5,1),
    set_temp_c11 DECIMAL(5,1), set_temp_c12 DECIMAL(5,1),
    set_temp_c13 DECIMAL(5,1), set_temp_c14 DECIMAL(5,1),
    set_temp_c15 DECIMAL(5,1), set_temp_c16 DECIMAL(5,1),
    
    -- 乾燥桶溫度
    actual_temp_a_bucket DECIMAL(5,1),
    actual_temp_b_bucket DECIMAL(5,1),
    actual_temp_c_bucket DECIMAL(5,1),
    set_temp_a_bucket DECIMAL(5,1),
    set_temp_b_bucket DECIMAL(5,1),
    set_temp_c_bucket DECIMAL(5,1),
    
    -- 延押輪溫度
    actual_temp_top DECIMAL(5,1),
    actual_temp_mid DECIMAL(5,1),
    actual_temp_bottom DECIMAL(5,1),
    set_temp_top DECIMAL(5,1),
    set_temp_mid DECIMAL(5,1),
    set_temp_bottom DECIMAL(5,1),
    
    -- 機器參數
    line_speed DECIMAL(8,2),         -- 線速度 (M/min)
    screw_pressure DECIMAL(8,2),     -- 螺桿壓力 (psi)
    screw_output DECIMAL(5,2),       -- 螺桿壓出量 (%)
    left_pad_thickness DECIMAL(8,2), -- 左墊片厚度 (mm)
    right_pad_thickness DECIMAL(8,2), -- 右墊片厚度 (mm)
    current_amperage DECIMAL(8,2),   -- 電流量 (A)
    extruder_speed DECIMAL(8,2),     -- 押出機轉速 (rpm)
    quantitative_pressure DECIMAL(8,2), -- 定量壓力 (psi)
    quantitative_output DECIMAL(5,2), -- 定量輸出 (%)
    carriage DECIMAL(8,2),           -- 車台 (cm)
    filter_pressure DECIMAL(8,2),   -- 濾網壓力 (psi)
    screw_rotation_speed DECIMAL(8,2), -- 螺桿轉速 (rpm)
    
    record_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 3. P2階段 - 品質檢測數據
-- ========================================
CREATE TABLE IF NOT EXISTS p2_quality_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_no VARCHAR(20) NOT NULL REFERENCES production_lots(lot_no) ON DELETE CASCADE,
    
    sheet_width DECIMAL(8,3),        -- 板寬 (mm)
    thickness1 DECIMAL(8,3),         -- 厚度測量點1 (μm)
    thickness2 DECIMAL(8,3),         -- 厚度測量點2 (μm)
    thickness3 DECIMAL(8,3),         -- 厚度測量點3 (μm)
    thickness4 DECIMAL(8,3),         -- 厚度測量點4 (μm)
    thickness5 DECIMAL(8,3),         -- 厚度測量點5 (μm)
    thickness6 DECIMAL(8,3),         -- 厚度測量點6 (μm)
    thickness7 DECIMAL(8,3),         -- 厚度測量點7 (μm)
    
    appearance SMALLINT,             -- 外觀品質 (0=不良, 1=良好)
    rough_edge SMALLINT,             -- 粗糙邊緣 (0=不良, 1=良好)
    slitting_result SMALLINT,        -- 分切結果 (0=不良, 1=良好)
    
    measurement_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 4. P3階段 - 最終檢驗數據
-- ========================================
CREATE TABLE IF NOT EXISTS p3_inspection_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_no VARCHAR(20) NOT NULL REFERENCES production_lots(lot_no) ON DELETE CASCADE,
    
    p3_no VARCHAR(50),               -- P3編號 (如 2411012_04_34_301)
    e_value INTEGER,                 -- E值
    po_10 SMALLINT,                  -- 10PO檢測
    burr SMALLINT,                   -- 毛邊檢測
    shift SMALLINT,                  -- 位移檢測
    iron SMALLINT,                   -- 鐵質檢測
    mold SMALLINT,                   -- 模具檢測
    rubber_wheel SMALLINT,           -- 橡膠輪檢測
    clean SMALLINT,                  -- 清潔度檢測
    adjustment_record SMALLINT,      -- 調整記錄
    finish SMALLINT,                 -- 完成狀態 (0=未完成, 1=已完成)
    
    inspection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 5. 品質測量詳細記錄
-- ========================================
CREATE TABLE IF NOT EXISTS quality_measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_no VARCHAR(20) NOT NULL REFERENCES production_lots(lot_no) ON DELETE CASCADE,
    
    measurement_type VARCHAR(50),    -- 測量類型 (上一捲5點, 收料捲5點, QA抽驗)
    measurement_category VARCHAR(10), -- H or L
    point_1 DECIMAL(8,2),
    point_2 DECIMAL(8,2),
    point_3 DECIMAL(8,2),
    point_4 DECIMAL(8,2),
    point_5 DECIMAL(8,2),
    
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 6. 不良品記錄
-- ========================================
CREATE TABLE IF NOT EXISTS defect_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_no VARCHAR(20) NOT NULL REFERENCES production_lots(lot_no) ON DELETE CASCADE,
    
    defect_length VARCHAR(50),       -- 不良米數 (如 2500M)
    defect_type VARCHAR(100),        -- 不良狀況 (如 厚度異常)
    defect_position VARCHAR(200),    -- 不良位置 (如 01, 02, 19, 20)
    severity VARCHAR(20),            -- 嚴重程度
    
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- 7. 索引優化
-- ========================================
CREATE INDEX IF NOT EXISTS idx_production_lots_date ON production_lots(production_date);
CREATE INDEX IF NOT EXISTS idx_production_lots_phase ON production_lots(phase);
CREATE INDEX IF NOT EXISTS idx_p1_extrusion_lot ON p1_extrusion_data(lot_no);
CREATE INDEX IF NOT EXISTS idx_p2_quality_lot ON p2_quality_data(lot_no);
CREATE INDEX IF NOT EXISTS idx_p3_inspection_lot ON p3_inspection_data(lot_no);
CREATE INDEX IF NOT EXISTS idx_quality_measurements_lot ON quality_measurements(lot_no);
CREATE INDEX IF NOT EXISTS idx_defect_records_lot ON defect_records(lot_no);

-- ========================================
-- 8. 更新時間觸發器
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_production_lots_updated_at 
    BEFORE UPDATE ON production_lots 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 9. 資料完整性約束
-- ========================================
ALTER TABLE production_lots 
    ADD CONSTRAINT chk_phase CHECK (phase IN ('P1', 'P2', 'P3')),
    ADD CONSTRAINT chk_lot_no_format CHECK (lot_no ~ '^\d{7}_\d{2}$');

-- ========================================
-- 10. 視圖 - 生產數據彙總
-- ========================================
CREATE OR REPLACE VIEW production_summary AS
SELECT 
    pl.lot_no,
    pl.production_date,
    pl.product_spec,
    pl.material,
    pl.phase,
    pl.good_products,
    pl.defective_products,
    CASE WHEN pl.good_products + pl.defective_products > 0 
         THEN ROUND((pl.good_products::DECIMAL / (pl.good_products + pl.defective_products)) * 100, 2) 
         ELSE 0 END as quality_rate,
    COUNT(DISTINCT p1.id) as p1_records,
    COUNT(DISTINCT p2.id) as p2_records,
    COUNT(DISTINCT p3.id) as p3_records,
    COUNT(DISTINCT dr.id) as defect_count
FROM production_lots pl
LEFT JOIN p1_extrusion_data p1 ON pl.lot_no = p1.lot_no
LEFT JOIN p2_quality_data p2 ON pl.lot_no = p2.lot_no
LEFT JOIN p3_inspection_data p3 ON pl.lot_no = p3.lot_no
LEFT JOIN defect_records dr ON pl.lot_no = dr.lot_no
GROUP BY pl.lot_no, pl.production_date, pl.product_spec, pl.material, 
         pl.phase, pl.good_products, pl.defective_products;