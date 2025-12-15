"""remove_p3_lot_no_unique_constraint

Revision ID: 011dc47903ed
Revises: 2025_01_28_0100
Create Date: 2025-12-15 14:37:59.981809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011dc47903ed'
down_revision: Union[str, Sequence[str], None] = '2025_01_28_0100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    移除 P3 的 (lot_no, data_type) 唯一性約束
    
    原因：
    - 同一個批次(lot_no)可能會產生多個最終產品（不同 production_lot）
    - 每個產品的 product_id 本身就是唯一的
    - P3→P2 的追溯邏輯使用 (lot_no + source_winder)，一個 P3 只對應一筆 P2
    
    保留：
    - product_id unique index（在前一個 migration 已建立）
    """
    # 移除 P3 的 (lot_no, data_type) partial unique index
    op.execute("DROP INDEX IF EXISTS uq_records_p1_p3_lot_no_data_type")
    
    # 只為 P1 建立 (lot_no, data_type) unique index
    # P1 的設計是一個批次只有一筆記錄
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_records_p1_lot_no_data_type 
        ON records (lot_no, data_type) 
        WHERE data_type = 'P1'
    """)


def downgrade() -> None:
    """
    回復 P3 的 (lot_no, data_type) 唯一性約束
    """
    # 移除 P1 專用的 index
    op.execute("DROP INDEX IF EXISTS uq_records_p1_lot_no_data_type")
    
    # 恢復原本的 P1+P3 combined index
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_records_p1_p3_lot_no_data_type 
        ON records (lot_no, data_type) 
        WHERE data_type IN ('P1', 'P3')
    """)
