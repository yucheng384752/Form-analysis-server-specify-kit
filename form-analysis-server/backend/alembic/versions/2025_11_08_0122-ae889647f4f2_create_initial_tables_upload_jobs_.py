"""創建初始資料庫表格：upload_jobs、upload_errors、records

包含三個主要表格：
- upload_jobs: 檔案上傳工作記錄
- upload_errors: 上傳過程中的錯誤記錄  
- records: 成功驗證並匯入的業務資料

Revision ID: ae889647f4f2
Revises: 
Create Date: 2025-11-08 01:22:58.139379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ae889647f4f2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升級資料庫結構 - 創建所有表格和索引"""
    
    # 1. 創建 job_status_enum 列舉型別
    job_status_enum = postgresql.ENUM('PENDING', 'VALIDATED', 'IMPORTED', name='job_status_enum')
    job_status_enum.create(op.get_bind())
    
    # 2. 創建 upload_jobs 表格
    op.create_table(
        'upload_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='工作ID'),
        sa.Column('filename', sa.String(255), nullable=False, comment='上傳的檔案名稱'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='建立時間'),
        sa.Column('status', job_status_enum, nullable=False, server_default='PENDING', comment='處理狀態'),
        sa.Column('total_rows', sa.Integer(), nullable=True, comment='總行數'),
        sa.Column('valid_rows', sa.Integer(), nullable=True, comment='有效行數'),  
        sa.Column('invalid_rows', sa.Integer(), nullable=True, comment='無效行數'),
        sa.Column('process_id', postgresql.UUID(as_uuid=True), nullable=False, comment='處理流程識別碼，用於追蹤整個上傳處理過程'),
        sa.UniqueConstraint('process_id', name='uq_upload_jobs_process_id'),
    )
    
    # 3. 為 upload_jobs.process_id 創建索引
    op.create_index('ix_upload_jobs_process_id', 'upload_jobs', ['process_id'], unique=True)
    
    # 4. 創建 upload_errors 表格
    op.create_table(
        'upload_errors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='錯誤記錄ID'),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False, comment='關聯的上傳工作ID'),
        sa.Column('row_index', sa.Integer(), nullable=False, comment='發生錯誤的行索引（從0開始）'),
        sa.Column('field', sa.String(100), nullable=False, comment='發生錯誤的欄位名稱'),
        sa.Column('error_code', sa.String(50), nullable=False, comment='錯誤程式碼，如：INVALID_FORMAT、REQUIRED_FIELD等'),
        sa.Column('message', sa.String(500), nullable=False, comment='錯誤訊息描述'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='錯誤記錄建立時間'),
        sa.ForeignKeyConstraint(['job_id'], ['upload_jobs.id'], ondelete='CASCADE'),
    )
    
    # 5. 為 upload_errors 創建複合索引
    op.create_index('ix_upload_errors_job_id_row_index', 'upload_errors', ['job_id', 'row_index'])
    
    # 6. 創建 records 表格
    op.create_table(
        'records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='記錄ID'),
        sa.Column('lot_no', sa.String(50), nullable=False, comment='批號，格式：7數字_2數字（如：1234567_01）'),
        sa.Column('product_name', sa.String(100), nullable=False, comment='產品名稱，1-100字元'),
        sa.Column('quantity', sa.Integer(), nullable=False, comment='數量，非負整數'),
        sa.Column('production_date', sa.Date(), nullable=False, comment='生產日期，格式：YYYY-MM-DD'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='記錄建立時間'),
    )
    
    # 7. 為 records.lot_no 創建索引
    op.create_index('ix_records_lot_no', 'records', ['lot_no'])


def downgrade() -> None:
    """降級資料庫結構 - 刪除所有表格和索引"""
    
    # 按相反順序刪除，先刪除依賴的表格
    
    # 1. 刪除 records 表格索引和表格
    op.drop_index('ix_records_lot_no', table_name='records')
    op.drop_table('records')
    
    # 2. 刪除 upload_errors 表格索引和表格
    op.drop_index('ix_upload_errors_job_id_row_index', table_name='upload_errors')
    op.drop_table('upload_errors')
    
    # 3. 刪除 upload_jobs 表格索引和表格
    op.drop_index('ix_upload_jobs_process_id', table_name='upload_jobs')
    op.drop_table('upload_jobs')
    
    # 4. 刪除 job_status_enum 列舉型別
    job_status_enum = postgresql.ENUM(name='job_status_enum')
    job_status_enum.drop(op.get_bind())
