"""为会话增加独立、可回读的规划候选版本。

Revision ID: 20261016_01
Revises: 20261015_01
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op


revision = "20261016_01"
down_revision = "20261015_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建候选计划版本表；不触碰正式 Plan、Trip 或足迹数据。"""
    op.create_table(
        "plan_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.Column("conversation_uuid", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("target_plan_uuid", sa.String(length=32), nullable=True),
        sa.Column("target_plan_updated_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("brief", sa.JSON(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("conversation_uuid", "version", name="uk_plan_proposals_conversation_version"),
        sa.UniqueConstraint("conversation_uuid", "idempotency_key", name="uk_plan_proposals_conversation_key"),
    )
    op.create_index("idx_plan_proposals_user_conversation", "plan_proposals", ["user_uuid", "conversation_uuid"])


def downgrade() -> None:
    """只删除尚未写入正式记录的候选表；回滚前应先导出候选数据。"""
    op.drop_index("idx_plan_proposals_user_conversation", table_name="plan_proposals")
    op.drop_table("plan_proposals")
