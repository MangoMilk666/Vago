"""创建统一旅行空间观察表并迁移既有 GPS 与打卡事实。

Revision ID: 20260915_01
Revises: 20260913_01
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260915_01"
down_revision = "20260913_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """建立新主表，并以 Python 读取旧表保证迁移同时兼容 MySQL 与 SQLite。"""
    op.create_table(
        "travel_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=32), nullable=False),
        sa.Column("client_event_uuid", sa.String(length=64), nullable=False),
        sa.Column("user_uuid", sa.String(length=32), nullable=False),
        sa.Column("trip_uuid", sa.String(length=32), nullable=False),
        sa.Column("observation_type", sa.String(length=24), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("tracking_segment_uuid", sa.String(length=36), nullable=True),
        sa.Column("location_name", sa.String(length=256), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("user_uuid", "client_event_uuid", name="uk_travel_observations_user_client"),
    )
    op.create_index("idx_travel_observations_user_uuid", "travel_observations", ["user_uuid"])
    op.create_index("idx_travel_observations_trip_occurred_at", "travel_observations", ["trip_uuid", "occurred_at"])

    connection = op.get_bind()
    metadata = sa.MetaData()
    observations = sa.Table("travel_observations", metadata, autoload_with=connection)
    location_samples = sa.Table("location_samples", metadata, autoload_with=connection)
    checkins = sa.Table("checkins", metadata, autoload_with=connection)

    # 旧 GPS client_uuid 原样成为统一事件键，确保已上传队列仍能通过原 key 精确交接。
    location_rows = connection.execute(sa.select(location_samples)).mappings().all()
    if location_rows:
        connection.execute(
            observations.insert(),
            [
                {
                    "uuid": row["uuid"],
                    "client_event_uuid": row["client_uuid"],
                    "user_uuid": row["user_uuid"],
                    "trip_uuid": row["trip_uuid"],
                    "observation_type": "AUTO_GPS",
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "accuracy_m": row["accuracy_m"],
                    "speed_mps": row["speed_mps"],
                    "tracking_segment_uuid": row["tracking_segment_uuid"],
                    "location_name": None,
                    "note": None,
                    "occurred_at": row["recorded_at"],
                    "created_at": row["created_at"],
                }
                for row in location_rows
            ],
        )
    # 历史打卡没有客户端事件键；使用与自动 GPS 不会冲突的稳定前缀，不伪造设备 UUID。
    checkin_rows = connection.execute(sa.select(checkins)).mappings().all()
    if checkin_rows:
        connection.execute(
            observations.insert(),
            [
                {
                    "uuid": row["uuid"],
                    "client_event_uuid": f"legacy-checkin:{row['uuid']}",
                    "user_uuid": row["user_uuid"],
                    "trip_uuid": row["trip_uuid"],
                    "observation_type": "MANUAL_CHECKIN",
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "accuracy_m": None,
                    "speed_mps": None,
                    "tracking_segment_uuid": None,
                    "location_name": row["location_name"],
                    "note": row["note"],
                    "occurred_at": row["checked_at"],
                    "created_at": row["created_at"],
                }
                for row in checkin_rows
            ],
        )


def downgrade() -> None:
    """仅移除新观察表；兼容窗口内保留的旧事实表始终不受影响。"""
    op.drop_index("idx_travel_observations_trip_occurred_at", table_name="travel_observations")
    op.drop_index("idx_travel_observations_user_uuid", table_name="travel_observations")
    op.drop_table("travel_observations")
