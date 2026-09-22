"""增加 Web Agent 的长期会话与消息记录。

Revision ID: 20260922_02
Revises: 20260922_01
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260922_02"
down_revision = "20260922_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建按用户身份隔离的 Agent 会话和回放消息表。"""
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("use_rag", sa.Boolean(), nullable=False),
        sa.Column("use_personal_context", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("idx_agent_conversations_user_uuid", "agent_conversations", ["user_uuid"])
    op.create_index(
        "idx_agent_conversations_user_updated",
        "agent_conversations",
        ["user_uuid", "updated_at"],
    )
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("conversation_uuid", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=True),
        sa.Column("context_labels", sa.Text(), nullable=True),
        sa.Column("structured_plan", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("idx_agent_messages_conversation_uuid", "agent_messages", ["conversation_uuid"])
    op.create_index(
        "idx_agent_messages_conversation_id",
        "agent_messages",
        ["conversation_uuid", "id"],
    )


def downgrade() -> None:
    """删除会话数据表，不影响 Personal Context 的旅行事实。"""
    op.drop_index("idx_agent_messages_conversation_id", table_name="agent_messages")
    op.drop_index("idx_agent_messages_conversation_uuid", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("idx_agent_conversations_user_updated", table_name="agent_conversations")
    op.drop_index("idx_agent_conversations_user_uuid", table_name="agent_conversations")
    op.drop_table("agent_conversations")
