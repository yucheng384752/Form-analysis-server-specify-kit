-- 表單分析系統 - 初始資料庫結構
-- 生成時間: 2025-11-08
-- Alembic 版本: ae889647f4f2

-- 開始交易
BEGIN;

-- 創建 Alembic 版本控制表
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- 創建上傳工作狀態枚舉
CREATE TYPE job_status_enum AS ENUM ('PENDING', 'VALIDATED', 'IMPORTED');

-- 創建上傳工作表格
CREATE TABLE upload_jobs (
    id UUID NOT NULL,
    filename VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    status job_status_enum DEFAULT 'PENDING' NOT NULL,
    total_rows INTEGER,
    valid_rows INTEGER,
    invalid_rows INTEGER,
    process_id UUID NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_upload_jobs_process_id UNIQUE (process_id)
);

-- 添加表格註釋
COMMENT ON COLUMN upload_jobs.id IS '工作ID';
COMMENT ON COLUMN upload_jobs.filename IS '上傳的檔案名稱';
COMMENT ON COLUMN upload_jobs.created_at IS '建立時間';
COMMENT ON COLUMN upload_jobs.status IS '處理狀態';
COMMENT ON COLUMN upload_jobs.total_rows IS '總行數';
COMMENT ON COLUMN upload_jobs.valid_rows IS '有效行數';
COMMENT ON COLUMN upload_jobs.invalid_rows IS '無效行數';
COMMENT ON COLUMN upload_jobs.process_id IS '處理流程識別碼，用於追蹤整個上傳處理過程';

-- 為 process_id 創建唯一索引
CREATE UNIQUE INDEX ix_upload_jobs_process_id ON upload_jobs (process_id);

-- 創建上傳錯誤表格
CREATE TABLE upload_errors (
    id UUID NOT NULL,
    job_id UUID NOT NULL,
    row_index INTEGER NOT NULL,
    field VARCHAR(100) NOT NULL,
    error_code VARCHAR(50) NOT NULL,
    message VARCHAR(500) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(job_id) REFERENCES upload_jobs (id) ON DELETE CASCADE
);

-- 添加錯誤表格註釋
COMMENT ON COLUMN upload_errors.id IS '錯誤記錄ID';
COMMENT ON COLUMN upload_errors.job_id IS '關聯的上傳工作ID';
COMMENT ON COLUMN upload_errors.row_index IS '發生錯誤的行索引（從0開始）';
COMMENT ON COLUMN upload_errors.field IS '發生錯誤的欄位名稱';
COMMENT ON COLUMN upload_errors.error_code IS '錯誤代碼，如：INVALID_FORMAT、REQUIRED_FIELD等';
COMMENT ON COLUMN upload_errors.message IS '錯誤訊息描述';
COMMENT ON COLUMN upload_errors.created_at IS '錯誤記錄建立時間';

-- 為常查欄位創建複合索引
CREATE INDEX ix_upload_errors_job_id_row_index ON upload_errors (job_id, row_index);

-- 創建資料記錄表格
CREATE TABLE records (
    id UUID NOT NULL,
    lot_no VARCHAR(50) NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    production_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id)
);

-- 添加記錄表格註釋
COMMENT ON COLUMN records.id IS '記錄ID';
COMMENT ON COLUMN records.lot_no IS '批號，格式：7數字_2數字（如：1234567_01）';
COMMENT ON COLUMN records.product_name IS '產品名稱，1-100字元';
COMMENT ON COLUMN records.quantity IS '數量，非負整數';
COMMENT ON COLUMN records.production_date IS '生產日期，格式：YYYY-MM-DD';
COMMENT ON COLUMN records.created_at IS '記錄建立時間';

-- 為 lot_no 創建索引
CREATE INDEX ix_records_lot_no ON records (lot_no);

-- 插入 Alembic 版本記錄
INSERT INTO alembic_version (version_num) VALUES ('ae889647f4f2');

-- 提交交易
COMMIT;