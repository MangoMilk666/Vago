"""建立明确旅行偏好与 Grounded Travel Memory 的最小存储。

Revision ID: 20260922_01
Revises: 20260916_01
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260922_01"
down_revision = "20260916_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加 Phase 9 的偏好与旅行回忆表，不改写已有事实表。"""
    # 用户偏好数据表
    op.create_table(
        "travel_preferences",
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.Column("pace", sa.String(length=32), nullable=True),
        sa.Column("budget_level", sa.String(length=32), nullable=True),
        sa.Column("interests", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_uuid"),
    )
    # 旅行回忆数据表
    op.create_table(
        "travel_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.Column("trip_uuid", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("fact_snapshot", sa.Text(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("facts_refreshed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("user_uuid", "trip_uuid", name="uk_travel_memories_user_trip"),
    )
    op.create_index("idx_travel_memories_user_uuid", "travel_memories", ["user_uuid"])


def downgrade() -> None:
    """仅移除 Phase 9 新表，不影响既有 Trip 与 Observation 事实。"""
    op.drop_index("idx_travel_memories_user_uuid", table_name="travel_memories")
    op.drop_table("travel_memories")
    op.drop_table("travel_preferences")
