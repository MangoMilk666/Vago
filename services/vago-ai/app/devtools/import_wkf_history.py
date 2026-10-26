import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.agent_conversations.models import AgentConversation, AgentMessage
from app.core.database import SessionLocal
from app.plan_proposals.models import PlanProposal
from app.users.models import User
from app.wkf_import.models import WkfImportRecord


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _date(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _record(db, user_uuid: str, batch: str, key: str, kind: str, payload: object,
            target_kind: str | None = None, target_uuid: str | None = None) -> bool:
    digest = _hash(payload)
    existing = db.scalar(select(WkfImportRecord).where(
        WkfImportRecord.user_uuid == user_uuid, WkfImportRecord.source_key == key,
    ))
    if existing is not None:
        # 如果同一来源内容变化，停止导入；旧批次不可静默覆盖。
        if existing.source_hash != digest:
            raise ValueError(f"来源内容已变化：{key}")
        return False
    db.add(WkfImportRecord(
        user_uuid=user_uuid, source_key=key, source_hash=digest,
        source_kind=kind, source_payload=payload, target_kind=target_kind,
        target_uuid=target_uuid, batch_id=batch, created_at=_now(),
    ))
    db.flush()
    return True


def _conversation(db, user_uuid: str, batch: str, source_id: str,
                  created_at: datetime) -> AgentConversation:
    key = f"chat:{source_id}"
    mapping = db.scalar(select(WkfImportRecord).where(
        WkfImportRecord.user_uuid == user_uuid, WkfImportRecord.source_key == key,
    ))
    if mapping is not None:
        conversation = db.scalar(select(AgentConversation).where(
            AgentConversation.uuid == mapping.target_uuid,
            AgentConversation.user_uuid == user_uuid,
        ))
        if conversation is None:
            raise ValueError(f"来源会话映射已失效：{key}")
        return conversation
    conversation = AgentConversation(
        uuid=uuid4().hex, user_uuid=user_uuid, title="wkf 历史会话",
        use_rag=False, use_personal_context=False,
        created_at=created_at, updated_at=created_at,
    )
    db.add(conversation)
    db.flush()
    _record(db, user_uuid, batch, key, "conversation", {"legacy_chat_id": source_id},
            "conversation", conversation.uuid)
    return conversation


def _import_sessions(db, backup: Path, user_uuid: str, batch: str) -> dict[str, int]:
    counts = {"files": 0, "lines": 0, "visible_messages": 0, "internal_lines": 0, "new_messages": 0}
    for path in sorted((backup / "sessions").glob("session-*.jsonl")):
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        meta = next((item for item in lines if item.get("type") == "session_meta"), None)
        if meta is None or not isinstance(meta.get("session_key"), str):
            raise ValueError(f"会话文件缺少 session_meta：{path.name}")
        created = _date(meta.get("create_at"), _now())
        conversation = _conversation(db, user_uuid, batch, meta["session_key"], created)
        counts["files"] += 1
        for index, item in enumerate(lines, start=1):
            key = f"chatline:{meta['session_key']}:{index}"
            role = item.get("role")
            content = item.get("content")
            # 如果助手消息包含内部工具调用或没有正文，只归档来源，不伪装成用户可见回答。
            visible = role in {"user", "assistant"} and isinstance(content, str) and bool(content.strip())
            visible = visible and not item.get("tool_calls") and not item.get("tool_call_id")
            counts["visible_messages" if visible else "internal_lines"] += 1
            existing = db.scalar(select(WkfImportRecord).where(
                WkfImportRecord.user_uuid == user_uuid, WkfImportRecord.source_key == key,
            ))
            if existing is not None:
                _record(db, user_uuid, batch, key, "chat_line", item)
                counts["lines"] += 1
                continue
            message_uuid = None
            if visible:
                message_uuid = uuid4().hex
                db.add(AgentMessage(
                    uuid=message_uuid, conversation_uuid=conversation.uuid, role=role,
                    content=content, created_at=_date(item.get("create_at"), created),
                ))
                counts["new_messages"] += 1
            _record(db, user_uuid, batch, key, "chat_line", item,
                    "message" if visible else None, message_uuid)
            counts["lines"] += 1
    return counts


def _import_snapshots(db, backup: Path, user_uuid: str, batch: str) -> dict[str, int]:
    counts = {"snapshots": 0, "internal_messages": 0, "resource_candidates": 0}
    for path in sorted((backup / "domain-sessions").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != 1 or value.get("scope") != path.stem:
            raise ValueError(f"领域快照格式不匹配：{path.name}")
        _record(db, user_uuid, batch, f"snapshot:{path.stem}", "snapshot", value)
        counts["snapshots"] += 1
        for index, item in enumerate(value["messages"], start=1):
            _record(db, user_uuid, batch, f"domain-message:{path.stem}:{index}", "domain_message", item)
            counts["internal_messages"] += 1
        for artifact_id, artifact in value["artifacts"].items():
            if artifact.get("kind") != "candidate":
                raise ValueError(f"未知领域产物：{artifact_id}")
            _record(db, user_uuid, batch, f"domain-artifact:{path.stem}:{artifact_id}",
                    "resource_candidate", artifact)
            counts["resource_candidates"] += 1
    return counts


def _import_postgres(db, backup: Path, user_uuid: str, batch: str) -> int:
    rows = json.loads((backup / "postgres-proposals.json").read_text(encoding="utf-8"))
    count = 0
    for row in rows:
        source_key = f"postgres-proposal:{row['id']}"
        mapping = db.scalar(select(WkfImportRecord).where(
            WkfImportRecord.user_uuid == user_uuid, WkfImportRecord.source_key == source_key,
        ))
        if mapping is not None:
            _record(db, user_uuid, batch, source_key, "postgres_proposal", row)
            count += 1
            continue
        conversation = _conversation(db, user_uuid, batch, str(row["chat_id"]),
                                     _date(row["created_at"], _now()))
        version = (db.scalar(select(func.max(PlanProposal.version)).where(
            PlanProposal.conversation_uuid == conversation.uuid,
        )) or 0) + 1
        proposal = PlanProposal(
            uuid=uuid4().hex, user_uuid=user_uuid, conversation_uuid=conversation.uuid,
            version=version, idempotency_key=f"wkf:postgres:{row['id']}",
            request_fingerprint=_hash(row), target_kind="new_plan",
            status="PENDING_VALIDATION", brief={"legacyCity": row["city"]},
            content={"legacyPayload": row["payload"], "legacyWarnings": row["warnings"]},
            source_system="wkf", source_ref={"table": "itinerary_results", "id": row["id"],
                                             "version": row["version"], "planUuid": row["plan_uuid"]},
            created_at=_date(row["created_at"], _now()),
        )
        db.add(proposal)
        db.flush()
        _record(db, user_uuid, batch, source_key, "postgres_proposal", row,
                "proposal", proposal.uuid)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 wkf 历史数据到专用 Vago 测试账号")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--user-uuid", required=True)
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args()
    backup = args.backup_dir.resolve()
    hashes = json.loads((backup / "source-hashes.json").read_text(encoding="utf-8"))
    for name, expected in hashes.items():
        actual = hashlib.sha256((backup / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"来源备份哈希不匹配：{name}")
    with SessionLocal.begin() as db:
        if db.scalar(select(User.uuid).where(User.uuid == args.user_uuid)) is None:
            raise ValueError("指定的 Vago 测试账号不存在")
        sessions = _import_sessions(db, backup, args.user_uuid, args.batch_id)
        snapshots = _import_snapshots(db, backup, args.user_uuid, args.batch_id)
        proposals = _import_postgres(db, backup, args.user_uuid, args.batch_id)
    print(f"导入核数：主会话 {sessions}，领域快照 {snapshots}，PostgreSQL 候选 {proposals}")


if __name__ == "__main__":
    main()
