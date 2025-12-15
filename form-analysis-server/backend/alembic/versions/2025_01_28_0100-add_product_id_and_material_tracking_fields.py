"""add product_id and material tracking fields

Revision ID: 2025_01_28_0100
Revises: 2025_11_16_1543
Create Date: 2025-12-15 

此遷移添加 Product_ID 追蹤所需的欄位：
- material_code: 材料代號 (P1/P2)
- slitting_machine_number: 分條機編號 (P2)
- winder_number: 收卷機編號 (P2, 1-20)
- machine_no: 機台編號 (P3, 如 P24)
- mold_no: 模具編號 (P3, 如 238-2)
- production_lot: 生產批號 (P3, 如 301, 302)
- source_winder: 來源收卷機 (P3, 從 lot_no 提取)
- product_id: 產品識別碼 (P3, 格式: YYYY-MM-DD_machine_mold_lot)

同時調整唯一性約束：
- 移除舊的 (lot_no, data_type) 約束
- P1/P3: 使用 (lot_no, data_type) 部分唯一索引
- P2: 使用 (lot_no, data_type, winder_number) 部分唯一索引
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2025_01_28_0100'
down_revision: Union[str, None] = 'add_file_content_field'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    添加 Product_ID 追蹤欄位並調整唯一性約束
    """
    
    # 1. 添加新欄位
    # P1/P2 材料追蹤欄位
    op.add_column('records', sa.Column('material_code', sa.String(length=10), nullable=True, comment='材料代號 (H2, H5, H8)'))
    
    # P2 分條機追蹤欄位
    op.add_column('records', sa.Column('slitting_machine_number', sa.Integer(), nullable=True, comment='分條機編號 (1=分條1, 2=分條2)'))
    op.add_column('records', sa.Column('winder_number', sa.Integer(), nullable=True, comment='收卷機編號 (1-20)'))
    
    # P3 產品追蹤欄位
    op.add_column('records', sa.Column('machine_no', sa.String(length=20), nullable=True, comment='機台編號 (如 P24, P21)'))
    op.add_column('records', sa.Column('mold_no', sa.String(length=20), nullable=True, comment='模具編號 (如 238-2)'))
    op.add_column('records', sa.Column('production_lot', sa.Integer(), nullable=True, comment='生產批號 (如 301, 302, 303)'))
    op.add_column('records', sa.Column('source_winder', sa.Integer(), nullable=True, comment='來源收卷機編號 (從 lot_no 提取，用於 P3→P2 追蹤)'))
    op.add_column('records', sa.Column('product_id', sa.String(length=100), nullable=True, comment='產品識別碼 (格式: YYYY-MM-DD_machine_mold_lot)'))
    
    # 2. 建立新欄位的索引
    op.create_index('ix_records_material_code', 'records', ['material_code'], unique=False)
    op.create_index('ix_records_slitting_machine_number', 'records', ['slitting_machine_number'], unique=False)
    op.create_index('ix_records_winder_number', 'records', ['winder_number'], unique=False)
    op.create_index('ix_records_machine_no', 'records', ['machine_no'], unique=False)
    op.create_index('ix_records_mold_no', 'records', ['mold_no'], unique=False)
    op.create_index('ix_records_source_winder', 'records', ['source_winder'], unique=False)
    op.create_index('ix_records_product_id', 'records', ['product_id'], unique=True)
    
    # 3. 移除舊的唯一約束 (lot_no, data_type)
    # 這個約束不適用於 P2，因為 P2 需要支援 20 個收卷機
    # 使用 IF EXISTS 來避免約束不存在時的錯誤
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'uq_records_lot_no_data_type'
            ) THEN
                ALTER TABLE records DROP CONSTRAINT uq_records_lot_no_data_type;
            END IF;
        END $$;
    """)
    
    # 4. 建立新的部分唯一索引
    # P1 和 P3: 一個 lot_no 只有一筆記錄
    op.execute("""
        CREATE UNIQUE INDEX uq_records_p1_p3_lot_no_data_type 
        ON records (lot_no, data_type) 
        WHERE data_type IN ('P1', 'P3')
    """)
    
    # P2: 一個 lot_no 可以有多筆記錄 (不同收卷機)
    op.execute("""
        CREATE UNIQUE INDEX uq_records_p2_lot_no_data_type_winder 
        ON records (lot_no, data_type, winder_number) 
        WHERE data_type = 'P2'
    """)
    
    # 5. 為 additional_data 建立 GIN 索引 (用於 JSONB 快速查詢)
    # 注意: 只在欄位類型是 JSONB 時建立
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_records_additional_data_gin 
        ON records USING GIN (additional_data)
    """)


def downgrade() -> None:
    """
    回退：移除新欄位並還原舊的唯一約束
    """
    
    # 1. 移除 GIN 索引
    op.execute("DROP INDEX IF EXISTS ix_records_additional_data_gin")
    
    # 2. 移除部分唯一索引
    op.execute("DROP INDEX IF EXISTS uq_records_p2_lot_no_data_type_winder")
    op.execute("DROP INDEX IF EXISTS uq_records_p1_p3_lot_no_data_type")
    
    # 3. 還原舊的唯一約束
    # 在還原前，先刪除 P2 的重複資料 (保留 winder_number 最小的)
    op.execute("""
        DELETE FROM records
        WHERE data_type = 'P2' AND id NOT IN (
            SELECT DISTINCT ON (lot_no, data_type) id
            FROM records
            WHERE data_type = 'P2'
            ORDER BY lot_no, data_type, winder_number
        )
    """)
    
    op.create_unique_constraint(
        'uq_records_lot_no_data_type',
        'records',
        ['lot_no', 'data_type']
    )
    
    # 4. 移除新欄位的索引
    op.drop_index('ix_records_product_id', table_name='records')
    op.drop_index('ix_records_source_winder', table_name='records')
    op.drop_index('ix_records_mold_no', table_name='records')
    op.drop_index('ix_records_machine_no', table_name='records')
    op.drop_index('ix_records_winder_number', table_name='records')
    op.drop_index('ix_records_slitting_machine_number', table_name='records')
    op.drop_index('ix_records_material_code', table_name='records')
    
    # 5. 移除新欄位
    op.drop_column('records', 'product_id')
    op.drop_column('records', 'source_winder')
    op.drop_column('records', 'production_lot')
    op.drop_column('records', 'mold_no')
    op.drop_column('records', 'machine_no')
    op.drop_column('records', 'winder_number')
    op.drop_column('records', 'slitting_machine_number')
    op.drop_column('records', 'material_code')
