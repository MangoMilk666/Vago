"""验证 Agent 会话持久化、用户隔离与按页回放。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_conversations import service
from app.agent_conversations.schemas import ConversationCreateRequest, ConversationUpdateRequest
from app.core.database import Base
from app.core.exceptions import AppException


def _make_session() -> Session:
    """使用内存 SQLite 验证会话服务，不依赖本地 MySQL。"""
    from app.agent_conversations import models as _conversation_models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()


def test_agent_conversation_persists_messages_and_pages_history():
    """测试：首条消息生成标题，历史消息可按公开 UUID 向上翻页。"""
    db = _make_session()
    conversation = service.create_conversation(db, "user-a", ConversationCreateRequest())

    service.record_user_message(db, "user-a", conversation.uuid, "帮我规划京都三日行", True, True)
    service.record_assistant_message(db, "user-a", conversation.uuid, "可以先确认出行日期。")
    service.record_user_message(db, "user-a", conversation.uuid, "预算中等", False, True)

    page = service.get_messages(db, "user-a", conversation.uuid, limit=2)
    assert [message.content for message in page.messages] == ["可以先确认出行日期。", "预算中等"]
    assert page.next_before_uuid is not None

    previous_page = service.get_messages(
        db,
        "user-a",
        conversation.uuid,
        before_uuid=page.next_before_uuid,
        limit=2,
    )
    assert [message.content for message in previous_page.messages] == ["帮我规划京都三日行"]
    assert previous_page.next_before_uuid is None
    assert service.list_conversations(db, "user-a")[0].title == "帮我规划京都三日行"


def test_agent_conversation_is_isolated_per_user_and_deletes_messages():
    """测试：不同用户不能读取对话，删除会话时一并移除其回放消息。"""
    db = _make_session()
    conversation = service.create_conversation(db, "user-a", ConversationCreateRequest())
    service.record_user_message(db, "user-a", conversation.uuid, "我的行程", True, True)

    try:
        service.get_messages(db, "user-b", conversation.uuid)
    except AppException as exc:
        assert exc.code == "AGENT_CONVERSATION_NOT_FOUND"
    else:
        raise AssertionError("跨用户读取对话应被拒绝")

    service.delete_conversation(db, "user-a", conversation.uuid)
    assert service.list_conversations(db, "user-a") == []


def test_agent_conversation_title_can_be_renamed_by_its_owner():
    """测试：用户重命名应覆盖自动标题，并拒绝全空白输入。"""
    db = _make_session()
    conversation = service.create_conversation(db, "user-a", ConversationCreateRequest())

    updated = service.update_conversation(
        db,
        "user-a",
        conversation.uuid,
        ConversationUpdateRequest(title="  京都秋日安排  "),
    )
    assert updated.title == "京都秋日安排"

    try:
        service.update_conversation(
            db,
            "user-a",
            conversation.uuid,
            ConversationUpdateRequest(title="   "),
        )
    except AppException as exc:
        assert exc.code == "AGENT_CONVERSATION_TITLE_EMPTY"
    else:
        raise AssertionError("空白会话标题应被拒绝")
