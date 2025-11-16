"""添加 file_content 欄位到 upload_jobs 表

Revision ID: add_file_content_field
Revises: 2025_11_15_0001
Create Date: 2025-11-16 15:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_file_content_field'
down_revision: Union[str, Sequence[str], None] = '2025_11_15_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 file_content 欄位到 upload_jobs 表"""
    op.add_column('upload_jobs', sa.Column('file_content', sa.LargeBinary(), nullable=True, comment='上傳檔案的二進位內容，用於重新處理'))


def downgrade() -> None:
    """移除 file_content 欄位"""
    op.drop_column('upload_jobs', 'file_content')