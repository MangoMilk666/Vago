"""对齐 KnowledgeSource 与 legacy Guide 的 MySQL 排序规则。

Revision ID: 20260831_02
Revises: 20260831_01
Create Date: 2026-08-31
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260831_02"
down_revision = "20260831_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """统一为当前 legacy guides 使用的 utf8mb4_0900_ai_ci，避免跨表比较冲突。"""
    op.execute(
        "ALTER TABLE knowledge_sources "
        "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )


def downgrade() -> None:
    """回退到项目早期 DDL 中使用的 utf8mb4_unicode_ci。"""
    op.execute(
        "ALTER TABLE knowledge_sources "
        "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
