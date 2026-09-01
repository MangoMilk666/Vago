"""Personal Travel Knowledge API 路由。"""

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.dependencies.auth import get_current_user_uuid
from app.knowledge import indexing, service
from app.knowledge.schemas import (
    GuideCreateRequest,
    GuideResponse,
    GuideUpdateRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceResponse,
    KnowledgeSourceUpdateRequest,
)
from app.knowledge.storage import LocalKnowledgeStorage
from app.shared.responses import ApiResponse, success

router = APIRouter()

_ALLOWED_FILE_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
}


def _parse_tags(tags: str | None) -> list[str] | None:
    """解析 multipart 表单中的 JSON 标签列表。"""
    if not tags:
        return None
    try:
        parsed = json.loads(tags)
    except json.JSONDecodeError as exc:
        raise AppException("tags 必须是 JSON 字符串数组", status_code=400, code="PARAM_INVALID") from exc
    # 分支条件：multipart 标签不是字符串数组时，拒绝写入不一致的资料元数据。
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise AppException("tags 必须是 JSON 字符串数组", status_code=400, code="PARAM_INVALID")
    return parsed


@router.get("/sources", response_model=ApiResponse[list[KnowledgeSourceResponse]])
def list_sources(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[KnowledgeSourceResponse]]:
    """获取当前用户的个人知识源列表。"""
    return success(service.list_sources(db, user_uuid))


@router.get("/sources/{source_uuid}", response_model=ApiResponse[KnowledgeSourceResponse])
def get_source(
    source_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[KnowledgeSourceResponse]:
    """获取当前用户自己的个人知识源详情。"""
    return success(service.get_source(db, user_uuid, source_uuid))


@router.post("/sources", response_model=ApiResponse[KnowledgeSourceResponse])
def create_text_source(
    payload: KnowledgeSourceCreateRequest,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[KnowledgeSourceResponse]:
    """创建纯文本个人知识源；不会自动调用任何向量服务。"""
    return success(service.create_text_source(db, user_uuid, payload), "知识源创建成功")


@router.post("/sources/files", response_model=ApiResponse[KnowledgeSourceResponse])
async def upload_source_file(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=100),
    destination: str | None = Form(default=None, max_length=200),
    tags: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[KnowledgeSourceResponse]:
    """上传 UTF-8 编码的 .md 或 .txt 文件并同步提取可读文本。"""
    filename = file.filename or "knowledge.txt"
    suffix = Path(filename).suffix.lower()
    # 分支条件：当前 MVP 仅处理文本和 Markdown，不接受二进制办公文档。
    if suffix not in _ALLOWED_FILE_TYPES:
        raise AppException("当前仅支持上传 .md 或 .txt 文件", status_code=400, code="PARAM_INVALID")

    content = await file.read(settings.knowledge_max_file_bytes + 1)
    # 分支条件：文件超过本地 MVP 限制时，在写入 storage 前拒绝请求。
    if len(content) > settings.knowledge_max_file_bytes:
        raise AppException("文件超过知识源大小限制", status_code=400, code="PARAM_INVALID")
    try:
        content_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppException("当前仅支持 UTF-8 编码的文本文件", status_code=400, code="PARAM_INVALID") from exc
    # 分支条件：解析结果为空或超过现有索引链路上限时，不创建不可用的知识源。
    if not content_text.strip() or len(content_text) > settings.max_content_chars:
        raise AppException("文件内容为空或超过文本长度限制", status_code=400, code="PARAM_INVALID")

    source_uuid = service.new_source_uuid()
    storage = LocalKnowledgeStorage()
    storage_key = storage.put(source_uuid, filename, content)
    try:
        source = service.create_file_source(
            db,
            user_uuid,
            source_uuid=source_uuid,
            title=title.strip() if title and title.strip() else Path(filename).stem,
            original_filename=Path(filename).name,
            mime_type=_ALLOWED_FILE_TYPES[suffix],
            storage_key=storage_key,
            content_text=content_text,
            destination=destination,
            tags=_parse_tags(tags),
        )
    except Exception:
        # 数据库写入失败时回收刚保存的本地文件，避免遗留无主对象。
        storage.delete(storage_key)
        raise
    return success(source, "知识文件导入成功")


@router.put("/sources/{source_uuid}", response_model=ApiResponse[KnowledgeSourceResponse])
def update_source(
    source_uuid: str,
    payload: KnowledgeSourceUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[KnowledgeSourceResponse]:
    """更新个人知识源，并异步失效可能存在的旧向量索引。"""
    source = service.update_source(db, user_uuid, source_uuid, payload)
    background_tasks.add_task(indexing.delete_source_index_background, source.uuid, user_uuid)
    return success(source, "知识源更新成功")


@router.delete("/sources/{source_uuid}", response_model=ApiResponse[None])
def delete_source(
    source_uuid: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[None]:
    """软删除个人知识源，并尽力回收原文件和向量索引。"""
    storage_key = service.delete_source(db, user_uuid, source_uuid)
    background_tasks.add_task(indexing.delete_source_index_background, source_uuid, user_uuid)
    background_tasks.add_task(LocalKnowledgeStorage().delete, storage_key)
    return success(None, "知识源删除成功")


@router.post("/sources/{source_uuid}/index", response_model=ApiResponse[KnowledgeSourceResponse])
def index_source(
    source_uuid: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[KnowledgeSourceResponse]:
    """显式启用该资料的可选语义索引能力。"""
    # 分支条件：部署未启用 RAG capability 时，资料仍可使用，但不接受无效索引请求。
    if not settings.rag_enabled:
        raise AppException("当前环境未启用语义索引能力", status_code=503, code="RAG_UNAVAILABLE")
    source = service.mark_source_index_pending(db, user_uuid, source_uuid)
    background_tasks.add_task(indexing.index_source_background, source.uuid, user_uuid)
    return success(source, "知识源已加入语义索引队列")


@router.get("/guides/mine", response_model=ApiResponse[list[GuideResponse]])
def list_my_guides(
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[list[GuideResponse]]:
    """获取当前用户的个人旅行知识源列表。"""
    return success(service.list_my_guides(db, user_uuid))


@router.get("/guides/{guide_uuid}", response_model=ApiResponse[GuideResponse])
def get_my_guide_detail(
    guide_uuid: str,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """获取当前用户自己的知识源详情。"""
    return success(service.get_my_guide_detail(db, user_uuid, guide_uuid))


@router.post("/guides", response_model=ApiResponse[GuideResponse])
def create_guide(
    payload: GuideCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """创建个人旅行知识源；发布状态会进入后台索引队列。"""
    guide = service.create_guide(db, user_uuid, payload)
    # 分支条件：已发布知识源创建后，后台写入个人 RAG 知识库。
    if guide.status == service.GUIDE_STATUS_PUBLISHED:
        background_tasks.add_task(service.index_guide_background, guide.uuid, user_uuid)
    return success(guide, "攻略创建成功")


@router.put("/guides/{guide_uuid}", response_model=ApiResponse[GuideResponse])
def update_guide(
    guide_uuid: str,
    payload: GuideUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """更新个人旅行知识源；发布状态重建索引，草稿状态清理向量。"""
    guide = service.update_guide(db, user_uuid, guide_uuid, payload)
    # 分支条件：更新后仍是发布状态，后台重新索引。
    if guide.status == service.GUIDE_STATUS_PUBLISHED:
        background_tasks.add_task(service.index_guide_background, guide.uuid, user_uuid)
    else:
        # 分支条件：更新为草稿状态，后台清理已有向量。
        background_tasks.add_task(service.delete_guide_vectors_background, guide.uuid, user_uuid)
    return success(guide, "攻略更新成功")


@router.delete("/guides/{guide_uuid}", response_model=ApiResponse[None])
def delete_guide(
    guide_uuid: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[None]:
    """软删除个人旅行知识源，并在需要时清理向量库。"""
    should_delete_vectors = service.delete_guide(db, user_uuid, guide_uuid)
    # 分支条件：该知识源曾进入索引流程时，需要清理 Qdrant 文本块。
    if should_delete_vectors:
        background_tasks.add_task(service.delete_guide_vectors_background, guide_uuid, user_uuid)
    return success(None, "攻略删除成功")


@router.post("/guides/{guide_uuid}/index", response_model=ApiResponse[GuideResponse])
def index_guide(
    guide_uuid: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_uuid: str = Depends(get_current_user_uuid),
) -> ApiResponse[GuideResponse]:
    """手动触发知识源向量化。"""
    guide = service.mark_guide_pending(db, user_uuid, guide_uuid)
    background_tasks.add_task(service.index_guide_background, guide.uuid, user_uuid)
    return success(guide, "攻略已加入 AI 知识库索引队列")
