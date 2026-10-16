"""候选版本领域service层代码：归属、版本、幂等与草稿目标校验。"""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only

from app.agent_conversations.models import AgentConversation
from app.core.exceptions import AppException
from app.plan_proposals.models import PlanProposal
from app.plan_proposals.schemas import ProposalCreateRequest, ProposalDetail, ProposalStatus, ProposalSummary
from app.travel.models import Plan

PENDING_VALIDATION = "PENDING_VALIDATION"
MAX_CONTENT_BYTES = 256 * 1024


def create_proposal(
    db: Session, user_uuid: str, conversation_uuid: str, payload: ProposalCreateRequest
) -> ProposalDetail:
    """在已归属会话上串行分配版本；同一幂等键重复提交只返回原版本。"""
    try:
        serialized = json.dumps(
            payload.model_dump(mode="json", by_alias=True, exclude={"idempotency_key"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        # 如果候选中出现 NaN 等非标准 JSON 值，明确拒绝而不是落入未知 500。
        raise AppException("候选内容必须是有效 JSON", status_code=422, code="PLAN_PROPOSAL_INVALID_JSON") from exc
    # 如果候选内容过大，避免把未经约束的地图数据塞入单个 MySQL JSON 记录。
    if len(serialized.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise AppException("候选内容过大", status_code=413, code="PLAN_PROPOSAL_TOO_LARGE")
    # 这次候选请求内容的指纹：先把请求整理成稳定的 JSON 字符串，再用 SHA-256 算出一个摘要
    # 同一个 key、相同 fingerprint：说明是同一份候选的重复提交，返回之前创建的版本，不再新增。
    # 同一个 key、不同 fingerprint：说明拿旧 key 提交了另一份内容，返回 409，避免误把新方案当作旧请求的重试。
    fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    for attempt in range(3):
        try:
            # MySQL 的行锁将同一会话的版本分配串行化；UUID 与版本都由服务端生成。
            conversation = db.scalar(
                select(AgentConversation)
                .where(AgentConversation.uuid == conversation_uuid, AgentConversation.user_uuid == user_uuid)
                .with_for_update()
            )
            if conversation is None:
                raise AppException("对话不存在或无权访问", status_code=404, code="AGENT_CONVERSATION_NOT_FOUND")
            existing = db.scalar(
                select(PlanProposal).where(
                    PlanProposal.conversation_uuid == conversation_uuid,
                    PlanProposal.user_uuid == user_uuid,
                    PlanProposal.idempotency_key == payload.idempotency_key,
                )
            )
            # 如果相同幂等键已保存，请求内容必须完全一致。
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise AppException("幂等键已用于不同候选", status_code=409, code="PLAN_PROPOSAL_KEY_CONFLICT")
                result = _detail(existing)
                db.rollback()
                return result

            target_updated_at = None
            # 如果要编辑草稿，先核对目标归属及未转换状态；不允许候选指向他人的 Plan。
            if payload.target_kind == "draft_plan":
                target = db.scalar(
                    select(Plan).where(
                        Plan.uuid == payload.target_plan_uuid,
                        Plan.user_uuid == user_uuid,
                        Plan.deleted_at.is_(None),
                    )
                )
                if target is None:
                    raise AppException("计划不存在或无权访问", status_code=404, code="PLAN_NOT_FOUND")
                if target.status != 0 or target.converted_trip_uuid is not None:
                    raise AppException("只能选择未转换的草稿计划", status_code=409, code="PLAN_NOT_DRAFT")
                target_updated_at = target.updated_at

            last_version = db.scalar(
                select(func.max(PlanProposal.version)).where(PlanProposal.conversation_uuid == conversation_uuid)
            ) or 0
            proposal = PlanProposal(
                uuid=uuid4().hex,
                user_uuid=user_uuid,
                conversation_uuid=conversation_uuid,
                version=last_version + 1,
                idempotency_key=payload.idempotency_key,
                request_fingerprint=fingerprint,
                target_kind=payload.target_kind,
                target_plan_uuid=payload.target_plan_uuid,
                target_plan_updated_at=target_updated_at,
                status=PENDING_VALIDATION,
                brief=payload.brief,
                content=payload.content,
                source_system="vago",
            )
            db.add(proposal)
            db.commit()
            db.refresh(proposal)
            return _detail(proposal)
        except IntegrityError:
            # 如果并发事务撞上唯一约束，回滚后重读幂等键或重新分配版本。
            db.rollback()
            if attempt == 2:
                raise AppException("候选版本并发冲突，请重试", status_code=409, code="PLAN_PROPOSAL_VERSION_CONFLICT")
        except Exception:
            db.rollback()
            raise
    raise AssertionError("候选版本重试耗尽")


def list_proposals(db: Session, user_uuid: str, conversation_uuid: str) -> list[ProposalSummary]:
    """列出当前用户指定会话的候选版本。"""
    _require_conversation(db, user_uuid, conversation_uuid)
    items = db.scalars(
        select(PlanProposal)
        .where(PlanProposal.user_uuid == user_uuid, PlanProposal.conversation_uuid == conversation_uuid)
        .options(
            load_only(
                PlanProposal.uuid,
                PlanProposal.conversation_uuid,
                PlanProposal.version,
                PlanProposal.target_kind,
                PlanProposal.target_plan_uuid,
                PlanProposal.status,
                PlanProposal.created_at,
            )
        )
        .order_by(PlanProposal.version.desc())
    ).all()
    return [_summary(item) for item in items]


def get_proposal(db: Session, user_uuid: str, conversation_uuid: str, version: int) -> ProposalDetail:
    """按会话和版本读取完整候选，不接受其他用户的版本 ID。"""
    return _detail(_require_proposal(db, user_uuid, conversation_uuid, version))


def get_status(db: Session, user_uuid: str, conversation_uuid: str, version: int) -> ProposalStatus:
    """读取可回放的候选状态；阶段 2 不提供确认或状态变更入口。"""
    item = _require_proposal(db, user_uuid, conversation_uuid, version)
    return ProposalStatus(uuid=item.uuid, version=item.version, status=item.status)


def _require_conversation(db: Session, user_uuid: str, conversation_uuid: str) -> None:
    # 如果会话不属于当前账号，即使候选版本号存在也不泄露其存在性。
    if db.scalar(
        select(AgentConversation.id).where(
            AgentConversation.uuid == conversation_uuid, AgentConversation.user_uuid == user_uuid
        )
    ) is None:
        raise AppException("对话不存在或无权访问", status_code=404, code="AGENT_CONVERSATION_NOT_FOUND")


def _require_proposal(db: Session, user_uuid: str, conversation_uuid: str, version: int) -> PlanProposal:
    _require_conversation(db, user_uuid, conversation_uuid)
    item = db.scalar(
        select(PlanProposal).where(
            PlanProposal.user_uuid == user_uuid,
            PlanProposal.conversation_uuid == conversation_uuid,
            PlanProposal.version == version,
        )
    )
    if item is None:
        raise AppException("候选版本不存在", status_code=404, code="PLAN_PROPOSAL_NOT_FOUND")
    return item


def _summary(item: PlanProposal) -> ProposalSummary:
    '''
    封装ProposalSummary类
    '''
    return ProposalSummary(
        uuid=item.uuid,
        conversationUuid=item.conversation_uuid,
        version=item.version,
        targetKind=item.target_kind,
        targetPlanUuid=item.target_plan_uuid,
        status=item.status,
        createdAt=item.created_at,
    )


def _detail(item: PlanProposal) -> ProposalDetail:
    '''
    封装ProposalDetail类对象。
    '''
    return ProposalDetail(
        **_summary(item).model_dump(by_alias=True),
        targetPlanUpdatedAt=item.target_plan_updated_at,
        brief=item.brief,
        content=item.content,
    )
