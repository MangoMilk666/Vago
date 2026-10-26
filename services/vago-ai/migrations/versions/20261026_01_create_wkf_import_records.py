import sqlalchemy as sa
from alembic import op


revision = "20261026_01"
down_revision = "20261016_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """保存 wkf 历史记录的来源、内容和导入映射，供核数与撤回使用。"""
    op.create_table(
        "wkf_import_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_uuid", sa.String(36), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("target_kind", sa.String(32)),
        sa.Column("target_uuid", sa.String(32)),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_uuid", "source_key", name="uk_wkf_import_user_source"),
    )
    op.create_index("idx_wkf_import_user_batch", "wkf_import_records", ["user_uuid", "batch_id"])


def downgrade() -> None:
    """撤销导入记录表；执行前须先使用导入命令撤回对应数据。"""
    op.drop_index("idx_wkf_import_user_batch", table_name="wkf_import_records")
    op.drop_table("wkf_import_records")
