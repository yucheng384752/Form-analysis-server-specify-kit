"""add unique constraint lot_no data_type

Revision ID: 2025_11_15_0001
Revises: d0c4b28c0776
Create Date: 2025-11-15 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2025_11_15_0001'
down_revision: Union[str, None] = 'd0c4b28c0776'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    添加唯一約束到 records 表
    
    防止同一個 lot_no 和 data_type 組合出現重複資料。
    如果上傳相同批號的相同類型檔案(如 P1_2503033_01 上傳兩次)，
    第二次會被拒絕，防止資料重複。
    """
    # 在執行前，先刪除可能存在的重複資料
    # 只保留每個 (lot_no, data_type) 組合的最新一筆
    op.execute("""
        DELETE FROM records
        WHERE id NOT IN (
            SELECT DISTINCT ON (lot_no, data_type) id
            FROM records
            ORDER BY lot_no, data_type, created_at DESC
        )
    """)
    
    # 添加唯一約束
    op.create_unique_constraint(
        'uq_records_lot_no_data_type',
        'records',
        ['lot_no', 'data_type']
    )


def downgrade() -> None:
    """移除唯一約束"""
    op.drop_constraint(
        'uq_records_lot_no_data_type',
        'records',
        type_='unique'
    )
