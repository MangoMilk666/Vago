"""可选的本机 MySQL 候选版本回读验收；默认不运行写库路径。"""

import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select

from app.agent_conversations import service as conversations
from app.agent_conversations.schemas import ConversationCreateRequest
from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.plan_proposals import service as proposals
from app.plan_proposals.schemas import ProposalCreateRequest
from app.users.models import User

SAMPLE_PATH = Path(__file__).resolve().parents[3] / "docs/project-merge/phase-1/cases.json"


@pytest.mark.skipif(os.getenv("VAGO_MERGE_MYSQL_TEST") != "1", reason="需显式开启本机 MySQL 写入验收")
def test_mysql_proposal_round_trip_for_merge_account():
    """测试：仅在指定空测试账号短暂写入样例，跨 Session 回读并清理。"""
    user_uuid = "5519a1d427b249ed90e5fd9851224125"
    sample = json.loads(SAMPLE_PATH.read_text())["cases"][0]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.uuid == user_uuid, User.nickname == "wkf-merge-test"))
        assert user is not None, "专用测试账号不存在，拒绝写入其他账号"
        conversation = conversations.create_conversation(db, user_uuid, ConversationCreateRequest())

    try:
        with SessionLocal() as db:
            request = ProposalCreateRequest(
                idempotencyKey="mysql-phase2-sample-001",
                targetKind="new_plan",
                brief=sample["wkf_form"],
                content={"points": [{"id": "fictional-stop", "name": "示例地点"}], "routes": []},
            )
            created = proposals.create_proposal(db, user_uuid, conversation.uuid, request)
            assert created.version == 1
            assert proposals.create_proposal(db, user_uuid, conversation.uuid, request).uuid == created.uuid

        barrier = Barrier(2)

        def submit_parallel(key: str) -> int:
            """测试：不同请求从独立连接同时提交，仍由会话锁串行分配版本。"""
            with SessionLocal() as db:
                barrier.wait(timeout=5)
                return proposals.create_proposal(
                    db,
                    user_uuid,
                    conversation.uuid,
                    ProposalCreateRequest(
                        idempotencyKey=key,
                        targetKind="new_plan",
                        brief=sample["wkf_form"],
                        content={"points": [], "routes": []},
                    ),
                ).version

        with ThreadPoolExecutor(max_workers=2) as pool:
            versions = list(pool.map(submit_parallel, ["mysql-parallel-001", "mysql-parallel-002"]))
        assert set(versions) == {2, 3}

        with SessionLocal() as db:
            assert proposals.get_proposal(db, user_uuid, conversation.uuid, 1).brief["cities"] == ["示例城甲", "示例城乙"]
            assert proposals.get_status(db, user_uuid, conversation.uuid, 1).status == "PENDING_VALIDATION"
            assert [item.version for item in proposals.list_proposals(db, user_uuid, conversation.uuid)] == [3, 2, 1]
            with pytest.raises(AppException) as exc:
                proposals.get_proposal(db, "unrelated-user", conversation.uuid, 1)
            assert exc.value.status_code == 404
    finally:
        # 如果校验中途失败，仍只删除本次创建的会话及其候选，不动账号其他数据。
        with SessionLocal() as db:
            conversations.delete_conversation(db, user_uuid, conversation.uuid)
