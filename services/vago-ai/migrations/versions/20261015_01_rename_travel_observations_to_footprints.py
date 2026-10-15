"""Rename the unified travel observation table to travel footprints.

Revision ID: 20261015_01
Revises: 20260922_03
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op


revision = "20261015_01"
down_revision = "20260922_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """重命名统一足迹表及其类型列，保留所有现存记录。"""
    op.rename_table("travel_observations", "travel_footprints")
    op.alter_column(
        "travel_footprints",
        "observation_type",
        existing_type=sa.String(length=24),
        new_column_name="footprint_type",
    )
    op.drop_constraint("uk_travel_observations_user_client", "travel_footprints", type_="unique")
    op.create_unique_constraint(
        "uk_travel_footprints_user_client",
        "travel_footprints",
        ["user_uuid", "client_event_uuid"],
    )
    op.drop_index("idx_travel_observations_user_uuid", table_name="travel_footprints")
    op.drop_index("idx_travel_observations_trip_occurred_at", table_name="travel_footprints")
    op.create_index("idx_travel_footprints_user_uuid", "travel_footprints", ["user_uuid"])
    op.create_index(
        "idx_travel_footprints_trip_occurred_at",
        "travel_footprints",
        ["trip_uuid", "occurred_at"],
    )


def downgrade() -> None:
    """回退命名而不删改足迹点位数据。"""
    op.drop_index("idx_travel_footprints_trip_occurred_at", table_name="travel_footprints")
    op.drop_index("idx_travel_footprints_user_uuid", table_name="travel_footprints")
    op.drop_constraint("uk_travel_footprints_user_client", "travel_footprints", type_="unique")
    op.create_unique_constraint(
        "uk_travel_observations_user_client",
        "travel_footprints",
        ["user_uuid", "client_event_uuid"],
    )
    op.create_index("idx_travel_observations_user_uuid", "travel_footprints", ["user_uuid"])
    op.create_index(
        "idx_travel_observations_trip_occurred_at",
        "travel_footprints",
        ["trip_uuid", "occurred_at"],
    )
    op.alter_column(
        "travel_footprints",
        "footprint_type",
        existing_type=sa.String(length=24),
        new_column_name="observation_type",
    )
    op.rename_table("travel_footprints", "travel_observations")
