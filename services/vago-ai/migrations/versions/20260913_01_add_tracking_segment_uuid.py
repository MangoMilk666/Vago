"""为 GPS 样本增加连续记录段标识。

Revision ID: 20260913_01
Revises: 20260904_03
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260913_01"
down_revision = "20260904_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增可空段字段，历史 GPS 点继续依赖时间和距离推断断线。"""
    op.add_column("location_samples", sa.Column("tracking_segment_uuid", sa.String(length=36), nullable=True))


def downgrade() -> None:
    """回退本次段边界能力，不影响既有 GPS 事实记录。"""
    op.drop_column("location_samples", "tracking_segment_uuid")
