"""创建独立个人知识源表并迁移历史 Guide 数据。

Revision ID: 20260831_01
Revises:
Create Date: 2026-08-31
"""

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260831_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建新表，并在 legacy guides 存在时执行可重复的用户资料回填。"""
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("origin_url", sa.String(length=2048), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("destination", sa.String(length=200), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.String(length=16), nullable=False),
        sa.Column("parse_error", sa.String(length=1000), nullable=True),
        sa.Column("index_status", sa.String(length=16), nullable=False),
        sa.Column("index_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("uuid", name="uk_knowledge_sources_uuid"),
    )
    op.create_index("idx_knowledge_sources_user_uuid", "knowledge_sources", ["user_uuid"])
    op.create_index(
        "idx_knowledge_sources_user_created",
        "knowledge_sources",
        ["user_uuid", "created_at"],
    )

    # 分支条件：离线模式没有真实连接，无法探测 legacy guides；只生成建表 SQL。
    if context.is_offline_mode():
        return

    bind = op.get_bind()
    table_names = sa.inspect(bind).get_table_names()
    # 分支条件：历史环境含 guides 时复制个人资料；全新环境只保留空的新表。
    if "guides" not in table_names:
        return

    # 保留 Guide UUID 以复用既有 Qdrant points；重复执行时以 uuid 幂等覆盖迁移字段。
    op.execute(
        sa.text(
            """
            INSERT INTO knowledge_sources (
                uuid, user_uuid, title, source_type, mime_type, content_text,
                destination, tags, parse_status, index_status, created_at, updated_at
            )
            SELECT
                uuid,
                user_uuid,
                title,
                'TEXT',
                'text/plain',
                content,
                destination,
                tags,
                'READY',
                CASE
                    WHEN status = 0 THEN 'NOT_INDEXED'
                    WHEN ai_status IN (0, 1) THEN 'PENDING'
                    WHEN ai_status = 2 THEN 'INDEXED'
                    WHEN ai_status = 3 THEN 'FAILED'
                    ELSE 'NOT_INDEXED'
                END,
                created_at,
                updated_at
            FROM guides
            WHERE deleted_at IS NULL
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                content_text = VALUES(content_text),
                destination = VALUES(destination),
                tags = VALUES(tags),
                parse_status = VALUES(parse_status),
                index_status = VALUES(index_status),
                updated_at = VALUES(updated_at)
            """
        )
    )


def downgrade() -> None:
    """仅删除本次新增表；不会修改仍由 Java 使用的 legacy guides。"""
    op.drop_index("idx_knowledge_sources_user_created", table_name="knowledge_sources")
    op.drop_index("idx_knowledge_sources_user_uuid", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
