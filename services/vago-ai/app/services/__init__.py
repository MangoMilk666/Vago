"""
Services 包。

子模块职责说明：
  cleaner            - 文本清洗（HTML / emoji / 广告词 / 空白规范化）
  chunker            - 语义分块（tiktoken token 计数 + 递归中文边界切割）
  embedder           - OpenAI Embedding 向量化（批量 + 单条）
  metadata_extractor - 目的地识别与内容分类标签提取（关键词匹配）
  vector_store       - Qdrant CRUD（Collection 初始化 / upsert / search / delete）
  indexer            - RAG 管道编排（串联上述子模块，提供单一入库入口）
"""
