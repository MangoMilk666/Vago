import argparse
from collections import Counter

from sqlalchemy import select

from app.agent_conversations.models import AgentConversation, AgentMessage
from app.agent_conversations.service import get_messages
from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.devtools.import_wkf_history import _hash
from app.plan_proposals.models import PlanProposal
from app.users.models import User
from app.wkf_import.models import WkfImportRecord


def main() -> None:
    parser = argparse.ArgumentParser(description="核对或撤回一个 wkf 历史导入批次")
    parser.add_argument("--user-uuid", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    with SessionLocal.begin() as db:
        rows = db.scalars(select(WkfImportRecord).where(
            WkfImportRecord.user_uuid == args.user_uuid,
            WkfImportRecord.batch_id == args.batch_id,
        )).all()
        if not rows:
            raise ValueError("指定导入批次不存在")
        counts = Counter(row.source_kind for row in rows)
        targets = Counter()
        other_user_uuid = db.scalar(select(User.uuid).where(User.uuid != args.user_uuid).limit(1))
        if other_user_uuid is None:
            raise ValueError("缺少第二个真实账号，无法核对跨用户隔离")
        for row in rows:
            if _hash(row.source_payload) != row.source_hash:
                raise ValueError(f"导入来源内容哈希不匹配：{row.source_key}")
            if row.target_kind == "conversation":
                target = db.scalar(select(AgentConversation).where(
                    AgentConversation.uuid == row.target_uuid,
                    AgentConversation.user_uuid == args.user_uuid,
                ))
            elif row.target_kind == "message":
                target = db.scalar(select(AgentMessage).join(
                    AgentConversation,
                    AgentMessage.conversation_uuid == AgentConversation.uuid,
                ).where(
                    AgentMessage.uuid == row.target_uuid,
                    AgentConversation.user_uuid == args.user_uuid,
                ))
            elif row.target_kind == "proposal":
                target = db.scalar(select(PlanProposal).where(
                    PlanProposal.uuid == row.target_uuid,
                    PlanProposal.user_uuid == args.user_uuid,
                ))
            else:
                continue
            if target is None:
                raise ValueError(f"导入目标丢失或归属不符：{row.source_key}")
            if row.target_kind == "message" and target.content != row.source_payload.get("content"):
                raise ValueError(f"导入消息正文与来源不一致：{row.source_key}")
            if row.target_kind == "conversation":
                other_access = db.scalar(select(AgentConversation.id).where(
                    AgentConversation.uuid == row.target_uuid,
                    AgentConversation.user_uuid == other_user_uuid,
                ))
                if other_access is not None:
                    raise ValueError("导入会话可被其他账号读取")
            targets[row.target_kind] += 1
        # 如果会话被其他导入批次引用，拒绝撤回，避免删掉后来追加的历史。
        if args.rollback:
            conversation_ids = {row.target_uuid for row in rows if row.target_kind == "conversation"}
            mapped_messages = {row.target_uuid for row in rows if row.target_kind == "message"}
            mapped_proposals = {row.target_uuid for row in rows if row.target_kind == "proposal"}
            actual_messages = set(db.scalars(select(AgentMessage.uuid).where(
                AgentMessage.conversation_uuid.in_(conversation_ids),
            )).all())
            actual_proposals = set(db.scalars(select(PlanProposal.uuid).where(
                PlanProposal.conversation_uuid.in_(conversation_ids),
            )).all())
            if actual_messages != mapped_messages or actual_proposals != mapped_proposals:
                raise ValueError("导入会话已有其他消息或候选，拒绝删除")
            other = db.scalar(select(WkfImportRecord.id).where(
                WkfImportRecord.user_uuid == args.user_uuid,
                WkfImportRecord.batch_id != args.batch_id,
                WkfImportRecord.target_uuid.in_(conversation_ids),
            ).limit(1))
            if other is not None:
                raise ValueError("其他导入批次引用了这些会话，不能直接撤回")
            for row in rows:
                if row.target_kind == "message":
                    db.delete(db.scalar(select(AgentMessage).where(AgentMessage.uuid == row.target_uuid)))
                elif row.target_kind == "proposal":
                    db.delete(db.scalar(select(PlanProposal).where(PlanProposal.uuid == row.target_uuid)))
            db.flush()
            for row in rows:
                if row.target_kind == "conversation":
                    db.delete(db.scalar(select(AgentConversation).where(
                        AgentConversation.uuid == row.target_uuid,
                    )))
            for row in rows:
                db.delete(row)
        else:
            for row in rows:
                if row.target_kind != "conversation":
                    continue
                mapped_ids = [item.target_uuid for item in rows if item.target_kind == "message"]
                expected = len(db.scalars(select(AgentMessage.uuid).where(
                    AgentMessage.uuid.in_(mapped_ids),
                    AgentMessage.conversation_uuid == row.target_uuid,
                )).all())
                read_count = 0
                cursor = None
                while True:
                    page = get_messages(db, args.user_uuid, row.target_uuid, before_uuid=cursor)
                    read_count += len(page.messages)
                    if page.next_before_uuid is None:
                        break
                    cursor = page.next_before_uuid
                if read_count != expected:
                    raise ValueError("会话领域服务回读的消息数量不一致")
                try:
                    get_messages(db, other_user_uuid, row.target_uuid)
                except AppException as exc:
                    if exc.status_code != 404:
                        raise
                else:
                    raise ValueError("其他账号可通过会话领域服务读取导入消息")
    print(f"来源核数：{dict(counts)}；目标核数：{dict(targets)}")
    if args.rollback:
        print("该批次的 MySQL 历史记录已撤回；Neo4j 副本须单独撤回")


if __name__ == "__main__":
    main()
