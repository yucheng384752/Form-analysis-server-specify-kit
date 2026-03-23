-- Migration: Create p2_items_v2 and p3_items_v2 tables
-- Date: 2026-01-13
-- Purpose: 改用混合架構 - 主表(p2_records/p3_records) + 明細表(p2_items_v2/p3_items_v2)

-- ============================================
-- P2 Items V2 Table
-- ============================================
-- 儲存 P2 展開的 row data (每個 winder 一筆)
CREATE TABLE IF NOT EXISTS p2_items_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    p2_record_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    winder_number INTEGER NOT NULL,
    
    -- P2 資料欄位
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
    
    -- 原始 row data (JSON)
    row_data JSONB,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_p2_items_v2_p2_record 
        FOREIGN KEY (p2_record_id) REFERENCES p2_records(id) ON DELETE CASCADE,
    CONSTRAINT fk_p2_items_v2_tenant 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT uq_p2_items_v2_record_winder 
        UNIQUE (p2_record_id, winder_number)
);

-- Indexes for p2_items_v2
CREATE INDEX IF NOT EXISTS ix_p2_items_v2_p2_record_id ON p2_items_v2(p2_record_id);
CREATE INDEX IF NOT EXISTS ix_p2_items_v2_tenant_id ON p2_items_v2(tenant_id);
CREATE INDEX IF NOT EXISTS ix_p2_items_v2_winder_number ON p2_items_v2(winder_number);
CREATE INDEX IF NOT EXISTS ix_p2_items_v2_row_data_gin ON p2_items_v2 USING gin(row_data);

COMMENT ON TABLE p2_items_v2 IS 'P2 items table - stores expanded row data per winder';
COMMENT ON COLUMN p2_items_v2.p2_record_id IS 'Foreign key to p2_records';
COMMENT ON COLUMN p2_items_v2.row_data IS 'Original CSV row data in JSON format';


-- ============================================
-- P3 Items V2 Table
-- ============================================
-- 儲存 P3 展開的 row data
CREATE TABLE IF NOT EXISTS p3_items_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    p3_record_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    row_no INTEGER NOT NULL,
    
    -- P3 資料欄位
    product_id VARCHAR(100) UNIQUE,
    lot_no VARCHAR(50) NOT NULL,
    production_date DATE,
    machine_no VARCHAR(20),
    mold_no VARCHAR(50),
    production_lot INTEGER,
    source_winder INTEGER,
    specification VARCHAR(100),
    bottom_tape_lot VARCHAR(50),
    
    -- 原始 row data (JSON)
    row_data JSONB,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_p3_items_v2_p3_record 
        FOREIGN KEY (p3_record_id) REFERENCES p3_records(id) ON DELETE CASCADE,
    CONSTRAINT fk_p3_items_v2_tenant 
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT uq_p3_items_v2_record_row 
        UNIQUE (p3_record_id, row_no)
);

-- Indexes for p3_items_v2
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_p3_record_id ON p3_items_v2(p3_record_id);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_tenant_id ON p3_items_v2(tenant_id);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_lot_no ON p3_items_v2(lot_no);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_product_id ON p3_items_v2(product_id);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_machine_no ON p3_items_v2(machine_no);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_mold_no ON p3_items_v2(mold_no);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_source_winder ON p3_items_v2(source_winder);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_production_date ON p3_items_v2(production_date);
CREATE INDEX IF NOT EXISTS ix_p3_items_v2_row_data_gin ON p3_items_v2 USING gin(row_data);

COMMENT ON TABLE p3_items_v2 IS 'P3 items table - stores production details';
COMMENT ON COLUMN p3_items_v2.p3_record_id IS 'Foreign key to p3_records';
COMMENT ON COLUMN p3_items_v2.row_data IS 'Original CSV row data in JSON format';


-- ============================================
-- Updated At Triggers
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_p2_items_v2_updated_at ON p2_items_v2;
CREATE TRIGGER update_p2_items_v2_updated_at
    BEFORE UPDATE ON p2_items_v2
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_p3_items_v2_updated_at ON p3_items_v2;
CREATE TRIGGER update_p3_items_v2_updated_at
    BEFORE UPDATE ON p3_items_v2
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
