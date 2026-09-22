"""为 Agent 对话回放保存公开执行事件。

Revision ID: 20260922_03
Revises: 20260922_02
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op


revision = "20260922_03"
down_revision = "20260922_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加 JSON 文本列，仅持久化可向用户展示的 Agent 执行事件。"""
    op.add_column("agent_messages", sa.Column("agent_events", sa.Text(), nullable=True))


def downgrade() -> None:
    """回滚执行事件列，不影响已有对话正文和旅行领域事实。"""
    op.drop_column("agent_messages", "agent_events")
