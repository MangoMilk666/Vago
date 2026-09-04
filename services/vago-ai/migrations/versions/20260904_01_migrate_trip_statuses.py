"""将 Trip 状态从旧语义迁移为旅行生命周期。

Revision ID: 20260904_01
Revises: 20260831_03
Create Date: 2026-09-04
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260904_01"
down_revision = "20260831_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """保留旧已完成行程的历史语义，映射为新状态“已结束”。"""
    # 旧状态 2=已完成；新状态 2=进行中，因此必须先迁为 3=已结束。
    op.execute("UPDATE trips SET status = 3 WHERE status = 2")


def downgrade() -> None:
    """回退到旧状态定义时，将已结束恢复为旧已完成。"""
    # 新状态 3=已结束；旧状态 3=已取消，回退时优先保护历史完成语义。
    op.execute("UPDATE trips SET status = 2 WHERE status = 3")
