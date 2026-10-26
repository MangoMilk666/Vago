import sqlalchemy as sa
from alembic import op


revision = "20261026_02"
down_revision = "20261026_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为既有候选增加可回读的确定性校验报告。"""
    op.add_column("plan_proposals", sa.Column("validation_result", sa.JSON(), nullable=True))
    op.add_column("plan_proposals", sa.Column("validated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """删除校验报告字段；降级前应导出已存结果。"""
    op.drop_column("plan_proposals", "validated_at")
    op.drop_column("plan_proposals", "validation_result")
