"""创建 iOS Travel Tracking 所需的 GPS 样本与手动打卡表。

Revision ID: 20260904_03
Revises: 20260904_02
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260904_03"
down_revision = "20260904_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建足迹事实表及用户、行程维度的查询索引。"""
    op.create_table(
        "location_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("client_uuid", sa.String(length=64), nullable=False),
        sa.Column("user_uuid", sa.String(length=32), nullable=False),
        sa.Column("trip_uuid", sa.String(length=32), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("user_uuid", "client_uuid", name="uk_location_samples_user_client"),
    )
    op.create_index("idx_location_samples_user_uuid", "location_samples", ["user_uuid"])
    op.create_index("idx_location_samples_trip_uuid", "location_samples", ["trip_uuid"])
    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("user_uuid", sa.String(length=32), nullable=False),
        sa.Column("trip_uuid", sa.String(length=32), nullable=False),
        sa.Column("location_name", sa.String(length=256), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("idx_checkins_user_uuid", "checkins", ["user_uuid"])
    op.create_index("idx_checkins_trip_uuid", "checkins", ["trip_uuid"])


def downgrade() -> None:
    """回退时删除 Phase 8 新增表，不影响既有旅行核心表。"""
    op.drop_index("idx_checkins_trip_uuid", table_name="checkins")
    op.drop_index("idx_checkins_user_uuid", table_name="checkins")
    op.drop_table("checkins")
    op.drop_index("idx_location_samples_trip_uuid", table_name="location_samples")
    op.drop_index("idx_location_samples_user_uuid", table_name="location_samples")
    op.drop_table("location_samples")
