#!/usr/bin/env python3
"""
RAG 全链路端到端测试脚本。

使用方法（在 vago-ai/ 目录下运行）：
    python tests/e2e_rag_test.py

前置条件：
    - .env 已配置 LLM_API_KEY / EMBED_API_KEY（或其他兼容 Provider 的变量）
    - Qdrant 已启动：docker run -p 6333:6333 qdrant/qdrant
    - test.txt 已编辑好攻略内容，放置于 vago-ai/ 根目录

测试覆盖范围（按阶段顺序执行）：
    Phase 0  Qdrant Collection 初始化
    Phase 1  攻略入库（RAG Indexing Pipeline）
             - 文本清洗 → 元数据提取 → 语义分块 → Embedding → Qdrant 写入
    Phase 2  非流式 Agent 对话（run_agent_chat）
             - 观察 Agent 工具调用决策与最终完整回答
    Phase 3  流式 Agent 对话（stream_agent_chat，SSE）
             - 观察 token 级事件推送、searching 事件、sources 事件
    Phase 4  清理（可选）
             - 删除测试向量数据（KEEP_VECTORS=True 时跳过）
"""

import asyncio
import hashlib
import json
import logging
import sys
import uuid
from pathlib import Path

# ── 日志配置（必须在 import app 模块之前完成）────────────────────────────────
#
# 分级策略：
#   app.*        DEBUG   — 自有模块全量日志，展示管道每一步
#   langchain.*  INFO    — LangChain 框架日志，过滤 DEBUG 噪声
#   qdrant_client INFO   — Qdrant SDK 连接与操作
#   httpx / openai WARNING — HTTP 层仅输出错误，不刷屏请求详情

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.INFO)
logging.getLogger("langchain_core").setLevel(logging.INFO)
logging.getLogger("langchain_openai").setLevel(logging.INFO)
logging.getLogger("qdrant_client").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("app").setLevel(logging.DEBUG)   # 自有模块全量

logger = logging.getLogger("e2e_test")

# ── sys.path 设置：保证从 tests/ 子目录可以 import app ───────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # vago-ai/
sys.path.insert(0, str(PROJECT_ROOT))

# ── 应用模块（在 sys.path 设置完成后导入）─────────────────────────────────────
from app.models.schemas import ChatMessage, IngestRequest            # noqa: E402
from app.services.indexer import index_article                       # noqa: E402
from app.services.rag_chain import run_agent_chat, stream_agent_chat # noqa: E402
from app.services.vector_store import delete_article_chunks, init_collection  # noqa: E402

# ─── 测试参数配置（按需修改）─────────────────────────────────────────────────

# 固定测试用户，所有测试数据都挂在这个 user_uuid 下
TEST_USER_UUID = "test-user-00000000-0000-0000-0000-000000000001"

# test.txt 路径（放置于 vago-ai/ 根目录）
TEST_TXT_PATH = PROJECT_ROOT / "test.txt"

# article_id 由内容 MD5 在运行时推导（见 _derive_article_id）：
#   - 同一 test.txt 内容 → 同一 ID → Qdrant 幂等 upsert，不会重复写入
#   - 修改 test.txt 内容 → 不同 ID → 作为新文章独立入库，旧文章向量继续保留

# 对话问题（Phase 2 / Phase 3 各发一轮）
FIRST_QUESTION  = "根据攻略内容，给我七天日本旅游推荐一个适合的行程安排。排除富士山这个选项"
FOLLOW_UP       = "东京有哪些餐厅推荐？"

# 是否保留 Qdrant 向量数据供后续手动调试（True = 跳过清理）
KEEP_VECTORS = True


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    """打印阶段分隔线，方便在日志中快速定位各 Phase 边界。"""
    bar = "=" * 65
    logger.info(bar)
    logger.info("  %s", title)
    logger.info(bar)


def _load_test_content() -> str:
    """
    从 test.txt 读取攻略原文。

    若文件不存在或内容为空则打印指引并退出，
    避免用空内容浪费 Embedding API 调用次数。
    """
    if not TEST_TXT_PATH.exists():
        logger.error("test.txt 不存在：%s", TEST_TXT_PATH)
        logger.error("请在 vago-ai/ 根目录创建 test.txt 并填入攻略内容后重新运行")
        sys.exit(1)

    content = TEST_TXT_PATH.read_text(encoding="utf-8").strip()
    if not content:
        logger.error("test.txt 为空，请填入攻略文本后重新运行")
        sys.exit(1)

    logger.info("已加载 test.txt：%d 字符", len(content))
    return content


def _derive_article_id(content: str) -> str:
    """
    从文章内容推导确定性 article_id（UUID5）。

    使用内容前 4096 字节的 MD5 作为命名空间种子，
    保证同一内容每次运行得到相同 ID（触发 Qdrant 幂等 upsert），
    内容不同则 ID 不同（作为独立文章入库）。

    参数:
        content: test.txt 的完整文本内容。

    返回:
        符合 UUID 格式的字符串，可直接用作 Qdrant point ID 的命名空间。
    """
    content_hash = hashlib.md5(content[:4096].encode("utf-8")).hexdigest()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"vago-e2e-{content_hash}"))


# ─── Phase 0：Qdrant 初始化 ───────────────────────────────────────────────────

async def phase0_init_qdrant() -> None:
    """
    确保 Qdrant Collection 已创建（幂等操作）。

    若 Qdrant 未启动，此步骤会抛出连接异常，明确提示用户先启动 Docker。
    """
    _section("Phase 0 - Qdrant Collection 初始化")
    try:
        await init_collection()
        logger.info("[Phase 0] Qdrant Collection 就绪")
    except Exception as exc:
        logger.error("[Phase 0] Qdrant 连接失败：%s", exc)
        logger.error("[Phase 0] 请先启动 Qdrant：docker run -p 6333:6333 qdrant/qdrant")
        sys.exit(1)


# ─── Phase 1：攻略入库 ────────────────────────────────────────────────────────

async def phase1_ingest(content: str, article_id: str) -> bool:
    """
    执行完整的 RAG Indexing Pipeline 并记录各子步骤的耗时与指标。

    调用 index_article()，内部依次执行：
      Step 1 内容长度校验
      Step 2 文本清洗（strip_html / strip_emoji / normalize）
      Step 3 元数据提取（destinations / categories）
      Step 4 语义分块（tiktoken BPE + 中文句边界）
      Step 5 Embedding 向量化（OpenAI / 兼容 Provider，批量）
      Step 6 Qdrant upsert（幂等，UUID5 point ID）

    各步骤的 DEBUG 日志由 indexer.py 自身输出。

    参数:
        content:    test.txt 的完整文本。
        article_id: 由内容 MD5 推导的确定性 UUID，同一内容多次运行幂等。

    返回:
        True = 入库成功；False = 入库失败（已打印原因）。
    """
    _section("Phase 1 - 攻略入库（RAG Indexing Pipeline）")

    request = IngestRequest(
        article_id=article_id,
        user_uuid=TEST_USER_UUID,
        title="E2E 测试攻略",
        raw_content=content,
        source_url="https://test.vago.app/e2e",
        destinations=None,  # 让 AI 自动提取，测试 metadata_extractor
    )

    logger.info("[Phase 1] 开始入库  article_id=%s  user=%s", article_id, TEST_USER_UUID)
    response = await index_article(request)

    if response.status.value == "INDEXED":
        logger.info(
            "[Phase 1] 入库成功  chunk_count=%d  destinations=%s  categories=%s",
            response.chunk_count, response.destinations, response.categories,
        )
        logger.info("[Phase 1] 处理消息：%s", response.message)
        return True
    else:
        logger.error("[Phase 1] 入库失败：%s", response.message)
        return False


# ─── Phase 2：非流式 Agent 对话 ───────────────────────────────────────────────

async def phase2_non_streaming() -> dict:
    """
    以非流式方式调用 RAG Agent，等待完整回答后打印结果。

    关注日志中的关键信息：
      - [rag_chain] Tool 调用 user=... query='...'  — Agent 决定检索时输出
      - [rag_chain] 非流式调用 user=... input='...' — 入口日志

    回答和来源引用以 print 形式输出，与 logger 格式区分。

    返回:
        run_agent_chat 的返回字典，供 Phase 3 构造多轮历史使用。
    """
    _section("Phase 2 - 非流式 Agent 对话（run_agent_chat）")

    messages = [ChatMessage(role="user", content=FIRST_QUESTION)]

    logger.info("[Phase 2] 问题：%s", FIRST_QUESTION)
    logger.info("[Phase 2] 等待 Agent 完整回答（含工具调用，通常需要 10-30s）...")

    result = await run_agent_chat(user_uuid=TEST_USER_UUID, messages=messages)

    logger.info("[Phase 2] 使用模型：%s", result["model"])
    logger.info("[Phase 2] 引用攻略来源数：%d", len(result["sources"]))
    for i, src in enumerate(result["sources"], 1):
        logger.info(
            "[Phase 2] 来源[%d]  title=%s  score=%.3f  source_uuid=%s",
            i, src.title, src.score, src.source_uuid,
        )

    # 回答内容以 print 直接输出，便于阅读（不带日志前缀）
    print()
    print("─" * 65)
    print("[Phase 2 完整回答]")
    print("─" * 65)
    print(result["answer"])
    print("─" * 65)
    print()

    return result


# ─── Phase 3：流式 Agent 对话 ─────────────────────────────────────────────────

async def phase3_streaming(prev_result: dict) -> None:
    """
    以流式（SSE）方式调用 RAG Agent，逐事件打印并还原打字机效果。

    SSE 事件类型：
      type=text      — token 文本块，拼接后为完整回答，print 直接输出不换行
      type=searching — Agent 正在调用 search_user_guides 工具（含检索词）
      type=sources   — 流结束前发送的来源引用列表
      type=error     — 生成过程中的错误
      [DONE]         — 流结束标记

    使用多轮对话历史（含 Phase 2 的问答），测试 chat_history 传递是否正确。
    """
    _section("Phase 3 - 流式 Agent 对话（stream_agent_chat，SSE 事件）")

    # 构造多轮历史：上一轮问答 + 本轮追问
    messages = [
        ChatMessage(role="user",      content=FIRST_QUESTION),
        ChatMessage(role="assistant", content=prev_result["answer"]),
        ChatMessage(role="user",      content=FOLLOW_UP),
    ]

    logger.info("[Phase 3] 追问（携带 %d 条历史）：%s", len(messages) - 1, FOLLOW_UP)
    logger.info("[Phase 3] 开始接收 SSE 流...")

    print()
    print("─" * 65)
    print("[Phase 3 流式回答]（token 实时输出）")
    print("─" * 65)

    collected_tokens: list[str] = []
    sources_received: list[dict] = []

    async for raw_sse in stream_agent_chat(user_uuid=TEST_USER_UUID, messages=messages):
        # raw_sse 格式为 "data: {...}\n\n" 或 "data: [DONE]\n\n"
        raw = raw_sse.strip()

        if raw == "data: [DONE]":
            logger.info("[Phase 3] 收到流结束标记 [DONE]")
            break

        if not raw.startswith("data: "):
            continue

        try:
            payload: dict = json.loads(raw[6:])
        except json.JSONDecodeError:
            logger.warning("[Phase 3] 无法解析 SSE payload：%s", raw)
            continue

        event_type = payload.get("type")

        if event_type == "text":
            token = payload.get("content", "")
            collected_tokens.append(token)
            print(token, end="", flush=True)  # 打字机效果

        elif event_type == "searching":
            # 打印检索事件前先换行，避免与 token 输出混叠
            print()
            logger.info("[Phase 3] Agent 触发工具调用  query='%s'", payload.get("query"))

        elif event_type == "sources":
            sources_received = payload.get("sources", [])
            logger.info("[Phase 3] 收到来源引用  count=%d", len(sources_received))
            for i, src in enumerate(sources_received, 1):
                logger.info(
                    "[Phase 3] 来源[%d]  title=%s  score=%.3f",
                    i, src.get("title"), src.get("score"),
                )

        elif event_type == "error":
            print()  # 换行
            logger.error("[Phase 3] Agent 返回错误：%s", payload.get("message"))

    total_chars = sum(len(t) for t in collected_tokens)
    print()
    print("─" * 65)
    print()
    logger.info(
        "[Phase 3] 流式完成  total_chars=%d  sources=%d",
        total_chars, len(sources_received),
    )


# ─── Phase 4：清理测试数据 ────────────────────────────────────────────────────

async def phase4_cleanup(article_id: str) -> None:
    """
    从 Qdrant 删除本次测试写入的向量点（幂等）。

    KEEP_VECTORS=True 时跳过，保留向量便于手动用 Qdrant Dashboard 核查结果。

    参数:
        article_id: 本次入库使用的 article_id，用于定向删除对应向量点。
    """
    _section("Phase 4 - 清理测试向量数据")

    if KEEP_VECTORS:
        logger.info(
            "[Phase 4] KEEP_VECTORS=True，跳过清理。向量已保留：article_id=%s  user=%s",
            article_id, TEST_USER_UUID,
        )
        logger.info("[Phase 4] 若需清理，将 KEEP_VECTORS 改为 False 后重新运行")
        return

    deleted = await delete_article_chunks(
        user_uuid=TEST_USER_UUID,
        article_id=article_id,
    )
    logger.info("[Phase 4] 已删除 %d 个测试向量点", deleted)


# ─── 主入口 ───────────────────────────────────────────────────────────────────

async def main() -> None:
    """
    按顺序执行全部测试阶段，任一阶段失败则终止后续执行。

    日志级别说明（快速查阅）：
      DEBUG  — app.* 模块内部逐步耗时、字符数、分块数等管道指标
      INFO   — 阶段进入、关键结果、来源引用
      WARNING — 非致命异常（如 SSE 解析失败）
      ERROR  — 入库失败、Qdrant 连接失败、Agent 错误
    """
    _section("Vago AI RAG 全链路端到端测试")
    logger.info("PROJECT_ROOT  : %s", PROJECT_ROOT)
    logger.info("TEST_USER_UUID: %s", TEST_USER_UUID)
    logger.info("TEST_TXT_PATH : %s", TEST_TXT_PATH)
    logger.info("KEEP_VECTORS  : %s", KEEP_VECTORS)

    # 先加载内容，再从内容推导 article_id（同文件 = 同 ID = 幂等 upsert）
    content = _load_test_content()
    article_id = _derive_article_id(content)
    logger.info("ARTICLE_ID    : %s  (MD5 of content[:4096])", article_id)

    await phase0_init_qdrant()

    indexed = await phase1_ingest(content, article_id)
    if not indexed:
        logger.error("Phase 1 失败，终止测试")
        sys.exit(1)

    prev_result = await phase2_non_streaming()
    await phase3_streaming(prev_result)
    await phase4_cleanup(article_id)

    _section("全部测试阶段完成")


if __name__ == "__main__":
    asyncio.run(main())
