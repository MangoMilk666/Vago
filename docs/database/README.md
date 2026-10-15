# 数据库文档

**当前约定：** [db_schema.sql](db_schema.sql) 是全新、空白本地数据库的初始化脚本，包含 `DROP TABLE IF EXISTS`；不要在已有用户数据的数据库执行。已有数据库由 `services/vago-ai/migrations/` 中的 Alembic 版本增量升级。表的现行字段与行为还应核对 SQLAlchemy 模型及对应迁移。

早期包含 `gps_tracks`、公共攻略与收藏夹、照片存档等方案的长篇设计已移至[历史草案](../archive/database-schema-2026-05-16.md)。该草案不是当前表结构，也不能作为新 migration 的依据。
