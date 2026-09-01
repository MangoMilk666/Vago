"""将 KnowledgeSource 列排序规则精确对齐 legacy guides。

Revision ID: 20260831_03
Revises: 20260831_02
Create Date: 2026-08-31
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260831_03"
down_revision = "20260831_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """以实际 legacy guides 的 utf8mb4_unicode_ci 对齐资料文本和 UUID 列。"""
    op.execute(
        "ALTER TABLE knowledge_sources "
        "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )


def downgrade() -> None:
    """恢复上一条迁移使用的 utf8mb4_0900_ai_ci。"""
    op.execute(
        "ALTER TABLE knowledge_sources "
        "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
