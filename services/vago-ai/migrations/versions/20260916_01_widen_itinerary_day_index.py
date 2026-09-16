"""扩大每日行程序号字段，支持超过 127 天的长行程。

Revision ID: 20260916_01
Revises: 20260915_01
Create Date: 2026-09-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "20260916_01"
down_revision = "20260915_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """将旧 TINYINT day_index 扩大为 SMALLINT，保留既有日程数据。"""
    op.alter_column(
        "itinerary_days",
        "day_index",
        existing_type=mysql.TINYINT(),
        type_=sa.SmallInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """降级会重新施加 127 天上限，仅在确认没有超范围数据时执行。"""
    op.alter_column(
        "itinerary_days",
        "day_index",
        existing_type=sa.SmallInteger(),
        type_=mysql.TINYINT(),
        existing_nullable=False,
    )
