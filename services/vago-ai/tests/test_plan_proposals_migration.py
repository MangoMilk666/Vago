"""隔离验证候选表迁移的升降级，不触碰本机 MySQL。"""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def test_plan_proposal_migration_up_and_down():
    """测试：候选表及两个唯一约束可建立，回滚只移除候选表。"""
    path = Path(__file__).resolve().parents[1] / "migrations/versions/20261016_01_create_plan_proposals.py"
    spec = importlib.util.spec_from_file_location("proposal_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20261015_01"

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert "plan_proposals" in inspect(connection).get_table_names()
        constraints = inspect(connection).get_unique_constraints("plan_proposals")
        assert {item["name"] for item in constraints} >= {
            "uk_plan_proposals_conversation_version",
            "uk_plan_proposals_conversation_key",
        }
        migration.downgrade()
        assert "plan_proposals" not in inspect(connection).get_table_names()
