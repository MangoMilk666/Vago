"""个人旅行知识源请求与响应 schema。"""

from datetime import datetime

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSourceType(str, Enum):
    """个人知识来源方式；文件格式由 MIME 类型表达。"""

    TEXT = "TEXT"
    URL = "URL"
    FILE = "FILE"


class ParseStatus(str, Enum):
    """原始资料转为可读文本的处理状态。"""

    PENDING = "PENDING"
    PARSING = "PARSING"
    READY = "READY"
    FAILED = "FAILED"


class IndexStatus(str, Enum):
    """可选语义索引能力的处理状态。"""

    NOT_INDEXED = "NOT_INDEXED"
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class KnowledgeSourceCreateRequest(BaseModel):
    """创建纯文本或已完成导入的个人知识源请求。"""

    # 知识源标题。
    title: str = Field(min_length=1, max_length=100)
    # 来源方式；当前公开创建接口仅接受 TEXT，URL 导入留待后续实现。
    source_type: KnowledgeSourceType = Field(default=KnowledgeSourceType.TEXT, alias="sourceType")
    # URL 来源原始地址；当前仅记录元数据，不在本轮抓取网页内容。
    origin_url: str | None = Field(default=None, alias="originUrl", max_length=2048)
    # 用户直接输入或已提取的文本内容。
    content_text: str | None = Field(default=None, alias="contentText", max_length=50000)
    # 旅行目的地辅助标签。
    destination: str | None = Field(default=None, max_length=200)
    # 用户自定义标签。
    tags: list[str] | None = None

    model_config = ConfigDict(populate_by_name=True)


class KnowledgeSourceUpdateRequest(BaseModel):
    """更新个人知识源请求；不允许改变已创建来源的 source_type。"""

    # 新标题；未传表示不修改。
    title: str | None = Field(default=None, min_length=1, max_length=100)
    # 新文本；未传表示不修改。
    content_text: str | None = Field(default=None, alias="contentText", min_length=1, max_length=50000)
    # 新目的地标签；未传表示不修改。
    destination: str | None = Field(default=None, max_length=200)
    # 新标签列表；未传表示不修改。
    tags: list[str] | None = None

    model_config = ConfigDict(populate_by_name=True)


class KnowledgeSourceResponse(BaseModel):
    """个人知识源响应，不泄露社区互动和发布字段。"""

    # 知识源业务 UUID。
    uuid: str
    # 知识源标题。
    title: str
    # 来源方式。
    source_type: KnowledgeSourceType = Field(alias="sourceType")
    # URL 来源原始地址。
    origin_url: str | None = Field(default=None, alias="originUrl")
    # 文件原始名称。
    original_filename: str | None = Field(default=None, alias="originalFilename")
    # 文件或文本 MIME 类型。
    mime_type: str | None = Field(default=None, alias="mimeType")
    # 原始文件对象 key；调用方不应将其视为公开 URL。
    storage_key: str | None = Field(default=None, alias="storageKey")
    # 可直接使用的文本内容。
    content_text: str | None = Field(default=None, alias="contentText")
    # 旅行目的地辅助标签。
    destination: str | None = None
    # 用户自定义标签。
    tags: list[str] = Field(default_factory=list)
    # 内容解析状态。
    parse_status: ParseStatus = Field(alias="parseStatus")
    # 内容解析失败原因。
    parse_error: str | None = Field(default=None, alias="parseError")
    # 可选语义索引状态。
    index_status: IndexStatus = Field(alias="indexStatus")
    # 语义索引失败原因。
    index_error: str | None = Field(default=None, alias="indexError")
    # 知识源创建时间。
    created_at: datetime = Field(alias="createdAt")
    # 知识源最近更新时间。
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class GuideCreateRequest(BaseModel):
    """创建个人旅行知识源请求。"""

    # 知识源标题。
    title: str = Field(min_length=1, max_length=100)
    # 目的地标签或地点描述。
    destination: str | None = Field(default=None, max_length=200)
    # 封面图对象存储 key。
    cover_image_key: str | None = Field(default=None, alias="coverImageKey", max_length=500)
    # 图片对象存储 key 列表。
    image_keys: list[str] | None = Field(default=None, alias="imageKeys")
    # 知识源正文。
    content: str = Field(min_length=1, max_length=50000)
    # 用户自定义标签列表。
    tags: list[str] | None = None
    # 状态，0=草稿，1=已发布/可索引。
    status: int | None = Field(default=None, ge=0, le=1)

    model_config = ConfigDict(populate_by_name=True)


class GuideUpdateRequest(BaseModel):
    """更新个人旅行知识源请求；None 表示不更新该字段。"""

    # 新知识源标题；未传表示不修改。
    title: str | None = Field(default=None, min_length=1, max_length=100)
    # 新目的地标签或地点描述；未传表示不修改。
    destination: str | None = Field(default=None, max_length=200)
    # 新封面图对象存储 key；未传表示不修改。
    cover_image_key: str | None = Field(default=None, alias="coverImageKey", max_length=500)
    # 新图片对象存储 key 列表；未传表示不修改。
    image_keys: list[str] | None = Field(default=None, alias="imageKeys")
    # 新知识源正文；未传表示不修改。
    content: str | None = Field(default=None, min_length=1, max_length=50000)
    # 新用户自定义标签列表；未传表示不修改。
    tags: list[str] | None = None
    # 新状态；未传表示不修改。
    status: int | None = Field(default=None, ge=0, le=1)

    model_config = ConfigDict(populate_by_name=True)


class GuideResponse(BaseModel):
    """个人旅行知识源响应，保持旧 GuideVO 字段兼容。"""

    # 知识源业务 UUID。
    uuid: str
    # 知识源标题。
    title: str
    # 目的地标签或地点描述。
    destination: str | None = None
    # 封面图对象存储 key。
    cover_image_key: str | None = Field(default=None, alias="coverImageKey")
    # 图片对象存储 key 列表。
    image_keys: list[str] = Field(default_factory=list, alias="imageKeys")
    # 知识源正文。
    content: str
    # 用户自定义标签列表。
    tags: list[str] = Field(default_factory=list)
    # 历史浏览量；个人知识链路暂不主动增长。
    view_count: int = Field(alias="viewCount")
    # 历史点赞数；仅兼容旧前端展示。
    like_count: int = Field(alias="likeCount")
    # 当前用户是否已点赞；个人知识链路不维护点赞状态。
    liked: bool | None = None
    # 状态，0=草稿，1=已发布/可索引。
    status: int
    # RAG 向量化状态。
    ai_status: int | None = Field(default=None, alias="aiStatus")
    # 作者用户 UUID。
    author_uuid: str | None = Field(default=None, alias="authorUuid")
    # 作者昵称。
    author_nickname: str | None = Field(default=None, alias="authorNickname")
    # 作者头像对象存储 key。
    author_avatar_key: str | None = Field(default=None, alias="authorAvatarKey")
    # 知识源创建时间。
    created_at: datetime = Field(alias="createdAt")
    # 知识源最近更新时间。
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
