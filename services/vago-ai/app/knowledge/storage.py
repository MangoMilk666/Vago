"""个人知识源的本地文件存储实现。

当前仅服务本地开发环境；后续 OSS、S3 或 R2 实现只需遵循相同的 put/delete
边界，不应渗入 KnowledgeSource 领域模型。
"""

from pathlib import Path

from app.core.config import settings


class LocalKnowledgeStorage:
    """以受控 storage key 保存和删除个人知识源原始文件。"""

    def __init__(self, root: str | None = None) -> None:
        # 配置路径可按环境替换，避免把本地文件系统细节写进领域服务。
        self.root = Path(root or settings.knowledge_storage_path)

    def put(self, source_uuid: str, filename: str, content: bytes) -> str:
        """保存原始文件并返回相对 storage key。"""
        safe_name = Path(filename).name
        storage_key = f"sources/{source_uuid}/{safe_name}"
        path = self.root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return storage_key

    def delete(self, storage_key: str | None) -> None:
        """删除由本模块生成的单个文件，忽略不存在的历史文件。"""
        if not storage_key:
            return
        path = self.root / storage_key
        # 分支条件：storage key 越出配置根目录时拒绝删除，防止路径穿越。
        if self.root.resolve() not in path.resolve().parents:
            return
        path.unlink(missing_ok=True)
