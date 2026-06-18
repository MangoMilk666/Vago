# Vago（叠迹）数据库设计文档

**数据库**：MySQL 8.0+  
**字符集**：`utf8mb4`（支持 emoji）  
**排序规则**：`utf8mb4_unicode_ci`  
**文档版本**：v0.1 | 2026-05-16

---

## 目录

1. [设计原则](#1-设计原则)
2. [ER 关系总览](#2-er-关系总览)
3. [模块一：用户与认证](#3-模块一用户与认证)
4. [模块二：攻略库](#4-模块二攻略库)
5. [模块：收藏夹](#5-模块收藏夹)
6. [模块三：AI 行程规划](#6-模块三ai-行程规划)
7. [模块四：出行打卡与轨迹](#7-模块四出行打卡与轨迹)
8. [模块五：图文存档](#8-模块五图文存档)
9. [模块六：统计汇总](#9-模块六统计汇总)
9. [索引策略汇总](#9-索引策略汇总)
10. [分区策略](#10-分区策略)
11. [Redis 数据结构补充](#11-redis-数据结构补充)

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **主键策略** | 内部自增 `BIGINT` 作为物理主键（JOIN 性能），对外暴露 `CHAR(36) UUID` 作为业务 ID，防止 ID 枚举攻击 |
| **软删除** | 所有用户核心数据表均有 `deleted_at` 字段，物理删除仅在用户注销/申请删除时触发 |
| **时间字段** | 统一使用 `DATETIME(3)`（毫秒精度），时区统一存 UTC，展示层转换 |
| **地理坐标** | 使用 MySQL `POINT` 类型（SRID=4326，WGS84）存储经纬度，配合空间索引 |
| **大文本** | 攻略原始全文（`raw_content`）、日志（`note`）存 `MEDIUMTEXT`，单字段上限约 16MB |
| **高写入分区** | GPS 轨迹表按月 `RANGE` 分区，降低单表数据量 |
| **向量数据** | 向量 Embedding 存于独立向量数据库（Milvus/Qdrant），MySQL 只存元数据与索引状态 |
| **文件存储** | 照片、附件的二进制内容存对象存储（OSS），MySQL 只存 `oss_key` 路径 |

---

## 2. ER 关系总览

```
users (1)
  ├── user_oauth_bindings (N)          -- 第三方登录绑定
  ├── user_settings (1)                -- 用户偏好设置
  │
  ├── articles (N)                     -- 攻略库
  │     └── article_tags (N)           -- 攻略标签（目的地/分类）
  │
  ├── collections (N)                  -- 收藏夹
  │     └── collection_items (N)       -- 收藏夹-攻略关联
  │
  ├── ai_sessions (N)                  -- AI 规划会话
  │     └── ai_messages (N)            -- 会话消息记录
  │
  ├── trip_plans (N)                   -- 行程计划
  │     ├── trip_plan_days (N)         -- 行程按天
  │     │     └── trip_plan_items (N)  -- 每天的活动项
  │     │
  │     └── trip_archives (1)          -- 行程存档（旅行后生成）
  │           ├── archive_entries (N)  -- 存档打卡点（含日志）
  │           │     └── entry_photos (N) -- 打卡点关联照片（中间表）
  │           └── photos (N)           -- 照片（归属行程存档）
  │
  ├── checkins (N)                     -- 手动打卡点
  │     └── checkin_photos (N)         -- 打卡即拍照片（中间表）
  │
  ├── gps_tracks (N)                   -- GPS 轨迹点（分区表）
  │
  └── user_travel_stats (1)            -- 旅行统计汇总（冗余表）
```

---

## 3. 模块一：用户与认证

### 3.1 `users` — 用户主表

```sql
CREATE TABLE users (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
    uuid          CHAR(36)        NOT NULL COMMENT '对外业务 ID（UUID v4）',
    phone         VARCHAR(20)     NULL     COMMENT '手机号（E.164 格式，如 +8613800138000）',
    email         VARCHAR(128)    NULL     COMMENT '邮箱（可选）',
    nickname      VARCHAR(64)     NOT NULL COMMENT '昵称',
    avatar_oss_key VARCHAR(512)   NULL     COMMENT '头像 OSS 路径',
    plan_type     TINYINT         NOT NULL DEFAULT 0 COMMENT '订阅套餐：0=免费版 1=付费版',
    article_quota SMALLINT        NOT NULL DEFAULT 50 COMMENT '攻略库配额上限（免费版50条）',
    ai_calls_today SMALLINT       NOT NULL DEFAULT 0 COMMENT '今日 AI 调用次数（Redis 主要计数，此字段为日终归档）',
    status        TINYINT         NOT NULL DEFAULT 1 COMMENT '账户状态：1=正常 2=封禁 3=注销中',
    created_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at    DATETIME(3)     NULL     COMMENT '注销时间（软删除）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid    (uuid),
    UNIQUE KEY uk_phone   (phone),
    UNIQUE KEY uk_email   (email),
    KEY idx_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户主表';
```

### 3.2 `user_oauth_bindings` — 第三方登录绑定

```sql
CREATE TABLE user_oauth_bindings (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id       BIGINT UNSIGNED NOT NULL COMMENT '关联 users.id',
    provider      VARCHAR(32)     NOT NULL COMMENT '登录方：wechat / apple / google',
    open_id       VARCHAR(128)    NOT NULL COMMENT '第三方平台用户唯一 ID',
    access_token  VARCHAR(512)    NULL     COMMENT '最新 Access Token（加密存储）',
    expires_at    DATETIME(3)     NULL     COMMENT 'Token 过期时间',
    created_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_provider_openid (provider, open_id),
    KEY idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方登录绑定';
```

### 3.3 `user_settings` — 用户偏好设置

```sql
CREATE TABLE user_settings (
    user_id              BIGINT UNSIGNED NOT NULL COMMENT '关联 users.id，一对一',
    gps_mode             TINYINT         NOT NULL DEFAULT 1 COMMENT 'GPS 采集模式：0=省电 1=标准 2=精细',
    fog_unlock_radius_m  SMALLINT        NOT NULL DEFAULT 300 COMMENT '迷雾解锁半径（米）',
    default_visibility   TINYINT         NOT NULL DEFAULT 0 COMMENT '存档默认可见性：0=私密 1=链接可见 2=公开',
    language             VARCHAR(10)     NOT NULL DEFAULT 'zh-CN',
    timezone             VARCHAR(64)     NOT NULL DEFAULT 'Asia/Shanghai',
    notification_checkin TINYINT         NOT NULL DEFAULT 1 COMMENT '行程结束提醒开关',
    updated_at           DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户偏好设置（一对一）';
```

---

## 4. 模块二：攻略库

### 4.1 `articles` — 攻略主表

```sql
CREATE TABLE articles (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid          CHAR(36)        NOT NULL COMMENT '对外业务 ID',
    user_id       BIGINT UNSIGNED NOT NULL COMMENT '所属用户',
    title         VARCHAR(256)    NOT NULL COMMENT '攻略标题（用户填写或 AI 提取）',
    source_url    VARCHAR(2048)   NULL     COMMENT '来源链接（小红书/公众号等）',
    source_type   TINYINT         NOT NULL DEFAULT 0 COMMENT '导入方式：0=手动粘贴 1=URL导入 2=分享接力 3=文件导入',
    raw_content   MEDIUMTEXT      NOT NULL COMMENT '原始全文内容',
    summary       VARCHAR(512)    NULL     COMMENT 'AI 自动提取的摘要（首次索引后填充）',
    char_count    INT             NOT NULL DEFAULT 0 COMMENT '原始内容字符数',
    index_status  TINYINT         NOT NULL DEFAULT 0 COMMENT 'RAG 索引状态：0=待处理 1=处理中 2=已完成 3=失败',
    index_error   VARCHAR(512)    NULL     COMMENT '索引失败原因',
    vector_ns_key VARCHAR(256)    NULL     COMMENT '向量数据库命名空间内的记录键（格式：user_{uid}_article_{id}）',
    chunk_count   SMALLINT        NOT NULL DEFAULT 0 COMMENT '切块数量（索引完成后记录）',
    created_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at    DATETIME(3)     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid (uuid),
    KEY idx_user_status    (user_id, index_status, deleted_at),
    KEY idx_user_created   (user_id, created_at),
    FULLTEXT KEY ft_title  (title) WITH PARSER ngram COMMENT '标题全文检索（中文）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户攻略库';
```

### 4.2 `article_tags` — 攻略标签

> 将目的地标签和内容分类标签统一存储，通过 `tag_type` 区分，避免多个关联表。

```sql
CREATE TABLE article_tags (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    article_id BIGINT UNSIGNED NOT NULL COMMENT '关联 articles.id',
    user_id    BIGINT UNSIGNED NOT NULL COMMENT '冗余字段，便于按用户过滤',
    tag_type   TINYINT         NOT NULL COMMENT '标签类型：1=目的地 2=内容分类',
    tag_value  VARCHAR(128)    NOT NULL COMMENT '标签值，如"云南""大理""美食""住宿"',
    PRIMARY KEY (id),
    KEY idx_article_id     (article_id),
    KEY idx_user_type_val  (user_id, tag_type, tag_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='攻略标签（目的地/分类）';
```

**`tag_type` 枚举说明：**

| 值 | 含义 | 示例 |
|----|------|------|
| 1 | 目的地 | 云南、大理、洱海 |
| 2 | 内容分类 | 交通、住宿、美食、景点、实用tips |

---

## 5. 模块：收藏夹

### 5.1 `collections` — 收藏夹

```sql
CREATE TABLE collections (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid          CHAR(36)        NOT NULL COMMENT '对外业务 ID',
    user_uuid     VARCHAR(36)     NOT NULL COMMENT '所属用户 UUID',
    name          VARCHAR(100)    NOT NULL COMMENT '收藏夹名称',
    type          TINYINT         NOT NULL DEFAULT 1 COMMENT '0=RAG(AI知识库) 1=NORMAL(普通收藏)',
    description   VARCHAR(255)    NULL     COMMENT '收藏夹描述',
    sort_order    INT             NOT NULL DEFAULT 0 COMMENT '排序序号（越小越靠前）',
    created_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid (uuid),
    KEY idx_user (user_uuid),
    KEY idx_user_sort (user_uuid, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏夹';
```

### 5.2 `collection_items` — 收藏夹-攻略关联

```sql
CREATE TABLE collection_items (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid            CHAR(36)        NOT NULL COMMENT '对外业务 ID',
    collection_uuid VARCHAR(36)     NOT NULL COMMENT '所属收藏夹 UUID',
    guide_uuid      VARCHAR(36)     NOT NULL COMMENT '被收藏的攻略 UUID',
    user_uuid       VARCHAR(36)     NOT NULL COMMENT '收藏者 UUID（冗余，加速按用户查询）',
    note            VARCHAR(200)    NULL     COMMENT '收藏时的备注',
    sort_order      INT             NOT NULL DEFAULT 0 COMMENT '收藏夹内排序',
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_collection_guide (collection_uuid, guide_uuid),
    KEY idx_user (user_uuid),
    KEY idx_collection (collection_uuid),
    KEY idx_guide (guide_uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏夹-攻略关联表';
```

---

## 6. 模块三：AI 行程规划

### 6.1 `ai_sessions` — AI 规划会话

```sql
CREATE TABLE ai_sessions (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid         CHAR(36)        NOT NULL,
    user_id      BIGINT UNSIGNED NOT NULL,
    title        VARCHAR(256)    NULL     COMMENT '会话标题（AI 从首条消息提取或用户命名）',
    trip_plan_id BIGINT UNSIGNED NULL     COMMENT '关联的行程计划（若用户已从本次会话生成行程）',
    status       TINYINT         NOT NULL DEFAULT 1 COMMENT '状态：1=进行中 2=已完成 3=已归档',
    created_at   DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at   DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid (uuid),
    KEY idx_user_created (user_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 行程规划会话';
```

### 6.2 `ai_messages` — 会话消息记录

```sql
CREATE TABLE ai_messages (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id      BIGINT UNSIGNED NOT NULL COMMENT '关联 ai_sessions.id',
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '冗余，便于数据隔离校验',
    role            TINYINT         NOT NULL COMMENT '消息角色：1=用户 2=AI',
    content         MEDIUMTEXT      NOT NULL COMMENT '消息文本内容',
    structured_data JSON            NULL     COMMENT 'AI 返回的结构化行程 JSON（仅 role=2 且包含行程时填充）',
    rag_sources     JSON            NULL     COMMENT 'RAG 检索命中的 article chunk 列表，格式：[{article_id, chunk_index, score}]',
    token_count     INT             NOT NULL DEFAULT 0 COMMENT '本条消息消耗 Token 数',
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_session_created (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 会话消息记录';
```

### 6.3 `trip_plans` — 行程计划

```sql
CREATE TABLE trip_plans (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid           CHAR(36)        NOT NULL,
    user_id        BIGINT UNSIGNED NOT NULL,
    ai_session_id  BIGINT UNSIGNED NULL     COMMENT '生成来源 AI 会话（手动创建时为 NULL）',
    title          VARCHAR(256)    NOT NULL COMMENT '行程标题，如"6天云南深度游"',
    destinations   JSON            NOT NULL COMMENT '目的地列表，如 ["云南","大理","丽江"]',
    start_date     DATE            NULL     COMMENT '计划出发日期（可为空，表示未确定）',
    end_date       DATE            NULL     COMMENT '计划结束日期',
    total_days     TINYINT         NOT NULL DEFAULT 1,
    budget_cny     DECIMAL(10,2)   NULL     COMMENT '预算（人民币元）',
    status         TINYINT         NOT NULL DEFAULT 0 COMMENT '状态：0=草稿 1=待执行 2=执行中 3=已完成',
    cover_oss_key  VARCHAR(512)    NULL     COMMENT '封面图 OSS 路径',
    created_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at     DATETIME(3)     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid (uuid),
    KEY idx_user_status   (user_id, status, deleted_at),
    KEY idx_user_date     (user_id, start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户行程计划';
```

### 6.4 `trip_plan_days` — 行程按天分组

```sql
CREATE TABLE trip_plan_days (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trip_plan_id BIGINT UNSIGNED NOT NULL COMMENT '关联 trip_plans.id',
    user_id      BIGINT UNSIGNED NOT NULL,
    day_index    TINYINT         NOT NULL COMMENT '第几天，从 1 开始',
    date         DATE            NULL     COMMENT '对应日历日期（可为空）',
    day_title    VARCHAR(128)    NULL     COMMENT '当天主题，如"洱海环线骑行"',
    PRIMARY KEY (id),
    UNIQUE KEY uk_plan_day  (trip_plan_id, day_index),
    KEY idx_trip_plan_id    (trip_plan_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行程计划按天分组';
```

### 6.5 `trip_plan_items` — 行程活动项

```sql
CREATE TABLE trip_plan_items (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    day_id          BIGINT UNSIGNED NOT NULL COMMENT '关联 trip_plan_days.id',
    trip_plan_id    BIGINT UNSIGNED NOT NULL COMMENT '冗余，便于直接按计划查询',
    user_id         BIGINT UNSIGNED NOT NULL,
    sort_order      SMALLINT        NOT NULL DEFAULT 0 COMMENT '当天内排序权重（升序）',
    time_slot       VARCHAR(32)     NULL     COMMENT '建议时间段，如"09:00-11:00"',
    category        TINYINT         NOT NULL DEFAULT 0 COMMENT '活动类型：0=景点 1=美食 2=住宿 3=交通 4=购物 5=其他',
    location_name   VARCHAR(256)    NOT NULL COMMENT '地点名称',
    geo             POINT           NULL     COMMENT '地点经纬度（SRID=4326）',
    address         VARCHAR(512)    NULL     COMMENT '详细地址',
    tips            TEXT            NULL     COMMENT 'AI 提取或用户填写的注意事项',
    source_article_id BIGINT UNSIGNED NULL   COMMENT '攻略来源（关联 articles.id）',
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_day_sort      (day_id, sort_order),
    KEY idx_trip_plan_id  (trip_plan_id),
    SPATIAL KEY sidx_geo  (geo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行程活动项（最小规划粒度）';
```

---

## 7. 模块四：出行打卡与轨迹

### 7.1 `checkins` — 手动打卡点

```sql
CREATE TABLE checkins (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid          CHAR(36)        NOT NULL,
    user_id       BIGINT UNSIGNED NOT NULL,
    trip_plan_id  BIGINT UNSIGNED NULL     COMMENT '关联的行程计划（可为空，未关联则归入"未归档足迹"）',
    location_name VARCHAR(256)    NULL     COMMENT '地点名称（可手动填写或反地理编码获取）',
    geo           POINT           NOT NULL COMMENT '打卡经纬度（SRID=4326）',
    altitude_m    SMALLINT        NULL     COMMENT '海拔（米）',
    category      TINYINT         NOT NULL DEFAULT 0 COMMENT '打卡分类：0=通用 1=景点 2=美食 3=住宿 4=交通',
    note          VARCHAR(512)    NULL     COMMENT '打卡简短备注',
    checked_at    DATETIME(3)     NOT NULL COMMENT '实际打卡时间（设备时间）',
    created_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at    DATETIME(3)     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid          (uuid),
    KEY idx_user_checked        (user_id, checked_at DESC),
    KEY idx_user_trip           (user_id, trip_plan_id),
    SPATIAL KEY sidx_geo        (geo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户手动打卡点';
```

### 7.2 `checkin_photos` — 打卡点即拍照片（中间关联表）

```sql
CREATE TABLE checkin_photos (
    checkin_id BIGINT UNSIGNED NOT NULL,
    photo_id   BIGINT UNSIGNED NOT NULL COMMENT '关联 photos.id',
    PRIMARY KEY (checkin_id, photo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='打卡点与照片关联';
```

### 7.3 `gps_tracks` — GPS 轨迹点（高写入分区表）

> **注意**：此表按 `recorded_at` 按月进行 `RANGE` 分区，单分区数据量可控。

```sql
CREATE TABLE gps_tracks (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id      BIGINT UNSIGNED NOT NULL,
    trip_plan_id BIGINT UNSIGNED NULL     COMMENT '关联行程（可为空）',
    geo          POINT           NOT NULL COMMENT '位置坐标（SRID=4326）',
    altitude_m   SMALLINT        NULL     COMMENT '海拔（米）',
    speed_kmh    DECIMAL(6,2)    NULL     COMMENT '瞬时速度（km/h）',
    accuracy_m   SMALLINT        NULL     COMMENT 'GPS 精度（米）',
    mode         TINYINT         NOT NULL DEFAULT 1 COMMENT '采集模式：0=省电 1=标准 2=精细',
    recorded_at  DATETIME(3)     NOT NULL COMMENT '设备记录时间（分区键）',
    PRIMARY KEY (id, recorded_at),
    KEY idx_user_time     (user_id, recorded_at),
    KEY idx_trip_time     (trip_plan_id, recorded_at),
    SPATIAL KEY sidx_geo  (geo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='GPS 轨迹点（高频写入，按月分区）'
PARTITION BY RANGE (TO_DAYS(recorded_at)) (
    PARTITION p202601 VALUES LESS THAN (TO_DAYS('2026-02-01')),
    PARTITION p202602 VALUES LESS THAN (TO_DAYS('2026-03-01')),
    PARTITION p202603 VALUES LESS THAN (TO_DAYS('2026-04-01')),
    PARTITION p202604 VALUES LESS THAN (TO_DAYS('2026-05-01')),
    PARTITION p202605 VALUES LESS THAN (TO_DAYS('2026-06-01')),
    PARTITION p202606 VALUES LESS THAN (TO_DAYS('2026-07-01')),
    PARTITION p202607 VALUES LESS THAN (TO_DAYS('2026-08-01')),
    PARTITION p202608 VALUES LESS THAN (TO_DAYS('2026-09-01')),
    PARTITION p202609 VALUES LESS THAN (TO_DAYS('2026-10-01')),
    PARTITION p202610 VALUES LESS THAN (TO_DAYS('2026-11-01')),
    PARTITION p202611 VALUES LESS THAN (TO_DAYS('2026-12-01')),
    PARTITION p202612 VALUES LESS THAN (TO_DAYS('2027-01-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

### 7.4 `fog_unlock_regions` — 迷雾解锁区域记录

> 迷雾瓦片的**实时渲染**由 Redis Bitmap 负责（详见第 11 节），此表存储持久化的**区域级解锁状态**，用于统计、数据迁移和 Redis 冷启动重建。

```sql
CREATE TABLE fog_unlock_regions (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     BIGINT UNSIGNED NOT NULL,
    region_type TINYINT         NOT NULL COMMENT '区域层级：1=国家 2=省/州 3=城市/县',
    region_code VARCHAR(32)     NOT NULL COMMENT '标准地区码（ISO 3166 国家码或行政区划代码）',
    region_name VARCHAR(128)    NOT NULL COMMENT '地区名称（冗余，查询展示用）',
    first_visited_at DATETIME(3) NOT NULL COMMENT '首次到访时间',
    visit_count  SMALLINT       NOT NULL DEFAULT 1 COMMENT '到访次数',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_region    (user_id, region_type, region_code),
    KEY idx_user_type            (user_id, region_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='迷雾解锁区域持久化记录';
```

---

## 8. 模块五：图文存档

### 8.1 `photos` — 照片元数据

```sql
CREATE TABLE photos (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid            CHAR(36)        NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    trip_archive_id BIGINT UNSIGNED NULL     COMMENT '归属行程存档（可为空，表示游离照片）',
    oss_key         VARCHAR(512)    NOT NULL COMMENT '压缩版本 OSS 路径（最长边 ≤ 2048px）',
    oss_key_origin  VARCHAR(512)    NULL     COMMENT '原图 OSS 路径（付费版才保留）',
    width           SMALLINT        NULL,
    height          SMALLINT        NULL,
    size_bytes      INT             NULL     COMMENT '压缩后文件大小（字节）',
    exif_geo        POINT           NULL     COMMENT 'EXIF 中提取的 GPS 坐标（SRID=4326）',
    exif_taken_at   DATETIME(3)     NULL     COMMENT 'EXIF 拍摄时间',
    taken_at        DATETIME(3)     NULL     COMMENT '最终使用的拍摄时间（EXIF 优先，无则用上传时间）',
    upload_status   TINYINT         NOT NULL DEFAULT 0 COMMENT '上传状态：0=上传中 1=已完成 2=失败',
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at      DATETIME(3)     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid           (uuid),
    KEY idx_user_created         (user_id, created_at DESC),
    KEY idx_archive              (trip_archive_id),
    SPATIAL KEY sidx_exif_geo    (exif_geo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='照片元数据（二进制存 OSS）';
```

### 8.2 `trip_archives` — 行程存档头

```sql
CREATE TABLE trip_archives (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    uuid           CHAR(36)        NOT NULL,
    user_id        BIGINT UNSIGNED NOT NULL,
    trip_plan_id   BIGINT UNSIGNED NOT NULL COMMENT '关联的行程计划（一对一）',
    title          VARCHAR(256)    NOT NULL COMMENT '存档标题（默认同行程计划标题）',
    cover_photo_id BIGINT UNSIGNED NULL     COMMENT '封面照片 ID',
    summary        TEXT            NULL     COMMENT '旅行总结文字（用户填写或 AI 生成）',
    total_days     TINYINT         NOT NULL DEFAULT 1,
    total_km       DECIMAL(10,2)   NULL     COMMENT '行程总里程（km，从 GPS 轨迹计算）',
    checkin_count  SMALLINT        NOT NULL DEFAULT 0 COMMENT '打卡点总数（冗余计数）',
    photo_count    SMALLINT        NOT NULL DEFAULT 0 COMMENT '照片总数（冗余计数）',
    visibility     TINYINT         NOT NULL DEFAULT 0 COMMENT '可见性：0=私密 1=链接可见 2=公开',
    share_token    CHAR(16)        NULL     COMMENT '链接分享码（visibility=1 时生成）',
    created_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid          (uuid),
    UNIQUE KEY uk_trip_plan_id  (trip_plan_id),
    UNIQUE KEY uk_share_token   (share_token),
    KEY idx_user_created        (user_id, created_at DESC),
    KEY idx_visibility          (visibility, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行程存档头信息';
```

### 8.3 `archive_entries` — 存档打卡点（含日志）

```sql
CREATE TABLE archive_entries (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trip_archive_id BIGINT UNSIGNED NOT NULL COMMENT '关联 trip_archives.id',
    user_id         BIGINT UNSIGNED NOT NULL,
    checkin_id      BIGINT UNSIGNED NULL     COMMENT '关联的原始打卡点（若来源于手动打卡）',
    location_name   VARCHAR(256)    NULL,
    geo             POINT           NULL     COMMENT '地点坐标（SRID=4326）',
    category        TINYINT         NOT NULL DEFAULT 0,
    note            MEDIUMTEXT      NULL     COMMENT '富文本日志（Markdown，最多 5000 字）',
    entry_time      DATETIME(3)     NULL     COMMENT '该条目对应的旅行时间点',
    sort_order      SMALLINT        NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    KEY idx_archive_sort  (trip_archive_id, sort_order),
    SPATIAL KEY sidx_geo  (geo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='存档打卡点（含图文日志）';
```

### 8.4 `entry_photos` — 存档打卡点与照片关联

```sql
CREATE TABLE entry_photos (
    entry_id   BIGINT UNSIGNED NOT NULL COMMENT '关联 archive_entries.id',
    photo_id   BIGINT UNSIGNED NOT NULL COMMENT '关联 photos.id',
    sort_order SMALLINT        NOT NULL DEFAULT 0 COMMENT '照片在该打卡点内的展示顺序',
    PRIMARY KEY (entry_id, photo_id),
    KEY idx_photo_id (photo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='存档打卡点与照片多对多';
```

---

## 9. 模块六：统计汇总

### 9.1 `user_travel_stats` — 旅行统计汇总（冗余聚合表）

> 此表为**读优化的冗余表**，避免每次统计页面都全表扫描 `gps_tracks` 和 `fog_unlock_regions`。由后台任务定期更新（每次行程存档完成后触发更新）。

```sql
CREATE TABLE user_travel_stats (
    user_id           BIGINT UNSIGNED NOT NULL COMMENT '关联 users.id，一对一',
    country_count     SMALLINT        NOT NULL DEFAULT 0 COMMENT '已探索国家数',
    province_count    SMALLINT        NOT NULL DEFAULT 0 COMMENT '已探索省份数（国内）',
    city_count        SMALLINT        NOT NULL DEFAULT 0 COMMENT '已探索城市数',
    total_km          DECIMAL(12,2)   NOT NULL DEFAULT 0.00 COMMENT '累计旅行里程（km）',
    trip_count        SMALLINT        NOT NULL DEFAULT 0 COMMENT '已完成行程数',
    checkin_count     INT             NOT NULL DEFAULT 0 COMMENT '累计手动打卡点数',
    photo_count       INT             NOT NULL DEFAULT 0 COMMENT '累计上传照片数',
    first_trip_date   DATE            NULL     COMMENT '第一次旅行日期',
    last_trip_date    DATE            NULL     COMMENT '最近一次旅行日期',
    updated_at        DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户旅行统计汇总（冗余聚合）';
```

---

## 9. 索引策略汇总

| 表 | 索引 | 类型 | 覆盖查询场景 |
|----|------|------|-------------|
| `users` | `(phone)` / `(email)` | UNIQUE | 登录查询 |
| `articles` | `(user_id, index_status, deleted_at)` | 复合 | 攻略库列表页过滤 |
| `articles` | `ft_title` | FULLTEXT NGRAM | 标题中文全文搜索 |
| `article_tags` | `(user_id, tag_type, tag_value)` | 复合 | 按目的地/分类筛选攻略 |
| `trip_plans` | `(user_id, status, deleted_at)` | 复合 | 行程列表分 Tab 展示 |
| `trip_plan_items` | `geo` | SPATIAL | 地图范围内行程点查询 |
| `checkins` | `(user_id, checked_at DESC)` | 复合 | 打卡历史时间线 |
| `checkins` | `geo` | SPATIAL | 地图范围内打卡点查询 |
| `gps_tracks` | `(user_id, recorded_at)` + 分区裁剪 | 复合 + 分区 | 指定行程的轨迹回放 |
| `photos` | `(user_id, created_at DESC)` | 复合 | 照片库时间线 |
| `photos` | `exif_geo` | SPATIAL | 按地图范围聚合照片 |
| `trip_archives` | `(visibility, created_at DESC)` | 复合 | 公开存档广场（P2 功能） |
| `fog_unlock_regions` | `(user_id, region_type, region_code)` | UNIQUE 复合 | 解锁状态幂等写入 |

---

## 10. 分区策略

### `gps_tracks` 分区维护

每月初由 DBA 脚本或定时任务添加新分区，防止写入落入 `p_future` 兜底分区（性能差）：

```sql
-- 示例：在 2026-12 月末添加 2027-01 分区
ALTER TABLE gps_tracks REORGANIZE PARTITION p_future INTO (
    PARTITION p202701 VALUES LESS THAN (TO_DAYS('2027-02-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

### 历史数据归档

`gps_tracks` 超过 **24 个月**的历史分区，考虑归档到冷存储（如 S3 + Athena 查询），并 DROP 原分区：

```sql
ALTER TABLE gps_tracks DROP PARTITION p202401;
```

---

## 11. Redis 数据结构补充

> MySQL 以外，以下数据使用 Redis 存储，此处记录 Key 设计规范。

| Key 模式 | 数据类型 | TTL | 用途 |
|---------|---------|-----|------|
| `fog:bitmap:{user_id}:{zoom}:{tile_x}:{tile_y}` | Bitmap | 永久（用户注销时清除） | 地图瓦片迷雾解锁状态，每个 bit 对应子瓦片 |
| `ai:ratelimit:{user_id}` | String (计数) | 至当天 23:59:59 | AI 每日调用次数限制 |
| `article:index:status:{article_id}` | String | 1h | 攻略索引进度轮询 |
| `session:token:{user_id}` | Hash | 2h | JWT Access Token 缓存（登出时主动删除） |
| `trip:active:{user_id}` | String | 24h | 用户当前正在执行的行程 ID（快速获取） |
| `gps:batch:{user_id}` | List | 5min | GPS 轨迹点批量缓冲队列（每 30s 或满 100 条落库） |
| `stats:hot:{user_id}` | Hash | 1h | `user_travel_stats` 热点缓存（统计页秒开） |

---

*文档维护：新增或修改表结构后，请同步更新此文档并记录变更版本。*
