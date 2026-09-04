"""合并重复每日行程并增加日期唯一约束。

Revision ID: 20260904_02
Revises: 20260904_01
Create Date: 2026-09-04
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260904_02"
down_revision = "20260904_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """将同一资料同一天的重复日程合并到最早创建的一条记录。"""
    # 先记录需要合并的 UUID 映射，随后把景点迁到保留日程，避免丢失用户输入。
    op.execute(
        """
        CREATE TEMPORARY TABLE itinerary_day_duplicates AS
        SELECT duplicate_day.uuid AS duplicate_uuid, canonical_day.uuid AS canonical_uuid
        FROM itinerary_days AS duplicate_day
        JOIN (
            SELECT ref_uuid, ref_type, day_date, MIN(id) AS canonical_id
            FROM itinerary_days
            GROUP BY ref_uuid, ref_type, day_date
            HAVING COUNT(*) > 1
        ) AS duplicate_group
          ON duplicate_day.ref_uuid = duplicate_group.ref_uuid
         AND duplicate_day.ref_type = duplicate_group.ref_type
         AND duplicate_day.day_date = duplicate_group.day_date
        JOIN itinerary_days AS canonical_day ON canonical_day.id = duplicate_group.canonical_id
        WHERE duplicate_day.id <> canonical_day.id
        """
    )
    op.execute(
        """
        UPDATE itinerary_spots AS spot
        JOIN itinerary_day_duplicates AS duplicate_day ON spot.day_uuid = duplicate_day.duplicate_uuid
        SET spot.day_uuid = duplicate_day.canonical_uuid
        """
    )
    op.execute(
        """
        DELETE day_row FROM itinerary_days AS day_row
        JOIN itinerary_day_duplicates AS duplicate_day ON day_row.uuid = duplicate_day.duplicate_uuid
        """
    )
    op.execute("DROP TEMPORARY TABLE itinerary_day_duplicates")
    op.create_unique_constraint(
        "uk_itinerary_days_ref_date",
        "itinerary_days",
        ["ref_uuid", "ref_type", "day_date"],
    )


def downgrade() -> None:
    """回退时移除唯一约束；已合并的重复日程不再还原。"""
    op.drop_constraint("uk_itinerary_days_ref_date", "itinerary_days", type_="unique")
