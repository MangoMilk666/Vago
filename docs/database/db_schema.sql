-- ============================================================
-- Vago (叠迹) — 全量数据库 DDL
-- 数据库：MySQL 8.0+  字符集：utf8mb4_unicode_ci
-- 一键重建：mysql -u root -p <password> vago < db_schema.sql
--
-- 表创建顺序：
--   1. users              用户主表
--   2. user_oauth_bindings 第三方登录绑定
--   3. user_settings      用户偏好设置
--   4. trips              正式行程
--   5. plans              旅行计划（草稿）
--   6. guides             旅游攻略
--   7. itinerary_days     每日行程主表
--   8. itinerary_spots    每日景点/打卡点
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 清空旧表（按依赖逆序 DROP，重建时幂等）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS itinerary_spots;
DROP TABLE IF EXISTS itinerary_days;
DROP TABLE IF EXISTS guides;
DROP TABLE IF EXISTS plans;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS user_settings;
DROP TABLE IF EXISTS user_oauth_bindings;
DROP TABLE IF EXISTS users;

-- ============================================================
-- 模块一：用户与认证
-- ============================================================

-- ------------------------------------------------------------
-- 用户主表（users）
-- status: 1=正常 2=封禁 3=注销中
-- ------------------------------------------------------------
CREATE TABLE users (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT      COMMENT '自增主键',
    uuid            CHAR(36)        NOT NULL                     COMMENT '对外业务 ID（UUID v4）',
    phone           VARCHAR(20)     DEFAULT NULL                 COMMENT '手机号（E.164 格式，如 +8613800138000）',
    email           VARCHAR(128)    DEFAULT NULL                 COMMENT '邮箱（可选）',
    nickname        VARCHAR(64)     NOT NULL                     COMMENT '昵称',
    avatar_oss_key  VARCHAR(512)    DEFAULT NULL                 COMMENT '头像 OSS 路径',
    plan_type       TINYINT         NOT NULL DEFAULT 0           COMMENT '订阅套餐：0=免费版 1=付费版',
    article_quota   SMALLINT        NOT NULL DEFAULT 50          COMMENT '攻略库配额上限（免费版50条）',
    ai_calls_today  SMALLINT        NOT NULL DEFAULT 0           COMMENT '今日 AI 调用次数（Redis 主要计数，此字段为日终归档）',
    status          TINYINT         NOT NULL DEFAULT 1           COMMENT '账户状态：1=正常 2=封禁 3=注销中',
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at      DATETIME(3)     DEFAULT NULL                 COMMENT '注销时间（软删除）',

    PRIMARY KEY (id),
    UNIQUE KEY uk_uuid              (uuid),
    UNIQUE KEY uk_phone             (phone),
    UNIQUE KEY uk_email             (email),
    INDEX      idx_status_created   (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户主表';


-- ------------------------------------------------------------
-- 第三方登录绑定（user_oauth_bindings）
-- provider: wechat / apple / google
-- ------------------------------------------------------------
CREATE TABLE user_oauth_bindings (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         BIGINT UNSIGNED NOT NULL                     COMMENT '关联 users.id',
    provider        VARCHAR(32)     NOT NULL                     COMMENT '登录方：wechat / apple / google',
    open_id         VARCHAR(128)    NOT NULL                     COMMENT '第三方平台用户唯一 ID',
    access_token    VARCHAR(512)    DEFAULT NULL                 COMMENT '最新 Access Token（加密存储）',
    expires_at      DATETIME(3)     DEFAULT NULL                 COMMENT 'Token 过期时间',
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),

    PRIMARY KEY (id),
    UNIQUE KEY uk_provider_openid   (provider, open_id),
    INDEX      idx_user_id          (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='第三方登录绑定';


-- ------------------------------------------------------------
-- 用户偏好设置（user_settings）
-- 与 users 一对一，user_id 即主键
-- ------------------------------------------------------------
CREATE TABLE user_settings (
    user_id                 BIGINT UNSIGNED NOT NULL             COMMENT '关联 users.id，一对一',
    gps_mode                TINYINT         NOT NULL DEFAULT 1   COMMENT 'GPS 采集模式：0=省电 1=标准 2=精细',
    fog_unlock_radius_m     SMALLINT        NOT NULL DEFAULT 300 COMMENT '迷雾解锁半径（米）',
    default_visibility      TINYINT         NOT NULL DEFAULT 0   COMMENT '存档默认可见性：0=私密 1=链接可见 2=公开',
    language                VARCHAR(10)     NOT NULL DEFAULT 'zh-CN',
    timezone                VARCHAR(64)     NOT NULL DEFAULT 'Asia/Shanghai',
    notification_checkin    TINYINT         NOT NULL DEFAULT 1   COMMENT '行程结束提醒开关',
    updated_at              DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),

    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户偏好设置（一对一）';


-- ============================================================
-- 模块二：旅行核心业务
-- ============================================================

-- ------------------------------------------------------------
-- 正式行程表（trips）
-- status: 1=计划中 2=已完成 3=已取消
-- ------------------------------------------------------------
CREATE TABLE trips (
    id              BIGINT          NOT NULL AUTO_INCREMENT      COMMENT '自增主键',
    uuid            VARCHAR(32)     NOT NULL                     COMMENT '对外业务 ID',
    user_uuid       VARCHAR(32)     NOT NULL                     COMMENT '归属用户 UUID',
    title           VARCHAR(100)    NOT NULL                     COMMENT '行程标题',
    destination     VARCHAR(200)    DEFAULT NULL                 COMMENT '主目的地',
    cover_image_key VARCHAR(500)    DEFAULT NULL                 COMMENT '封面图 OSS Key',
    start_date      DATE            NOT NULL                     COMMENT '出发日期',
    end_date        DATE            NOT NULL                     COMMENT '返回日期',
    status          TINYINT         NOT NULL DEFAULT 1           COMMENT '状态：1=计划中 2=已完成 3=已取消',
    created_at      DATETIME(3)     NOT NULL                     COMMENT '创建时间',
    updated_at      DATETIME(3)     NOT NULL                     COMMENT '更新时间',
    deleted_at      DATETIME(3)     DEFAULT NULL                 COMMENT '软删除时间（NULL=未删除）',

    PRIMARY KEY (id),
    UNIQUE KEY uk_trips_uuid        (uuid),
    INDEX      idx_trips_user_uuid  (user_uuid),
    INDEX      idx_trips_start_date (start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行程表';


-- ------------------------------------------------------------
-- 旅行计划表（plans）
-- 草稿态，可转为正式行程
-- status: 0=草稿 1=已转为正式行程
-- ------------------------------------------------------------
CREATE TABLE plans (
    id                  BIGINT          NOT NULL AUTO_INCREMENT  COMMENT '自增主键',
    uuid                VARCHAR(32)     NOT NULL                 COMMENT '对外业务 ID',
    user_uuid           VARCHAR(32)     NOT NULL                 COMMENT '归属用户 UUID',
    title               VARCHAR(100)    NOT NULL                 COMMENT '计划标题',
    destination         VARCHAR(200)    DEFAULT NULL             COMMENT '目标地点',
    start_date          DATE            DEFAULT NULL             COMMENT '计划出发日期（可空）',
    end_date            DATE            DEFAULT NULL             COMMENT '计划返回日期（可空）',
    budget              DECIMAL(10,2)   DEFAULT NULL             COMMENT '费用预算',
    budget_currency     VARCHAR(3)      NOT NULL DEFAULT 'CNY'   COMMENT '货币单位',
    notes               TEXT            DEFAULT NULL             COMMENT '备注/草稿内容',
    converted_trip_uuid VARCHAR(32)     DEFAULT NULL             COMMENT '已转换的行程 UUID',
    status              TINYINT         NOT NULL DEFAULT 0       COMMENT '状态：0=草稿 1=已转换',
    created_at          DATETIME(3)     NOT NULL                 COMMENT '创建时间',
    updated_at          DATETIME(3)     NOT NULL                 COMMENT '更新时间',
    deleted_at          DATETIME(3)     DEFAULT NULL             COMMENT '软删除时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_plans_uuid        (uuid),
    INDEX      idx_plans_user_uuid  (user_uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='旅行计划表（草稿）';


-- ------------------------------------------------------------
-- 旅游攻略表（guides）
-- status: 0=草稿 1=已发布
-- ------------------------------------------------------------
CREATE TABLE guides (
    id              BIGINT          NOT NULL AUTO_INCREMENT      COMMENT '自增主键',
    uuid            VARCHAR(32)     NOT NULL                     COMMENT '对外业务 ID',
    user_uuid       VARCHAR(32)     NOT NULL                     COMMENT '归属用户 UUID',
    title           VARCHAR(100)    NOT NULL                     COMMENT '攻略标题',
    destination     VARCHAR(200)    DEFAULT NULL                 COMMENT '目的地',
    cover_image_key VARCHAR(500)    DEFAULT NULL                 COMMENT '封面图 OSS Key',
    image_keys      TEXT            DEFAULT NULL                 COMMENT '图片列表（JSON 数组）',
    content         MEDIUMTEXT      NOT NULL                     COMMENT '攻略正文',
    tags            VARCHAR(500)    DEFAULT NULL                 COMMENT '标签列表（JSON 数组）',
    view_count      INT             NOT NULL DEFAULT 0           COMMENT '浏览量',
    like_count      INT             NOT NULL DEFAULT 0           COMMENT '点赞数',
    status          TINYINT         NOT NULL DEFAULT 1           COMMENT '状态：0=草稿 1=已发布',
    ai_status       TINYINT         DEFAULT NULL                 COMMENT 'RAG 向量化状态：NULL=草稿未索引 0=PENDING 1=INDEXING 2=INDEXED 3=FAILED',
    created_at      DATETIME(3)     NOT NULL                     COMMENT '创建时间',
    updated_at      DATETIME(3)     NOT NULL                     COMMENT '更新时间',
    deleted_at      DATETIME(3)     DEFAULT NULL                 COMMENT '软删除时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_guides_uuid           (uuid),
    INDEX      idx_guides_user_uuid     (user_uuid),
    INDEX      idx_guides_status_ctime  (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='旅游攻略表';


-- ============================================================
-- 模块三：每日行程（Itinerary）
-- ============================================================

-- ------------------------------------------------------------
-- 每日行程主表（itinerary_days）
--
-- ref_type: 1=行程(trip)  2=计划(plan)
-- ref_uuid: 对应 trips.uuid 或 plans.uuid
--
-- 注意：同一 ref 下同一日期允许存在多条记录（不设唯一约束），
-- 支持用户在同一日期创建多个分段（如：上午段/下午段，
-- 或两段旅程之间的交通中转日）。
-- ------------------------------------------------------------
CREATE TABLE itinerary_days (
    id              BIGINT          NOT NULL AUTO_INCREMENT      COMMENT '自增主键',
    uuid            VARCHAR(32)     NOT NULL                     COMMENT '对外业务 ID',
    ref_uuid        VARCHAR(32)     NOT NULL                     COMMENT '所属行程/计划 UUID',
    ref_type        TINYINT         NOT NULL                     COMMENT '归属类型：1=行程 2=计划',
    day_date        DATE            NOT NULL                     COMMENT '当日日期',
    day_index       TINYINT         NOT NULL                     COMMENT '第几天（1起始）',
    transportation  VARCHAR(200)    DEFAULT NULL                 COMMENT '出行方式（飞机/高铁/自驾…）',
    accommodation   VARCHAR(300)    DEFAULT NULL                 COMMENT '住宿地点/酒店名称',
    meal_breakfast  VARCHAR(200)    DEFAULT NULL                 COMMENT '早餐地点',
    meal_lunch      VARCHAR(200)    DEFAULT NULL                 COMMENT '午餐地点',
    meal_dinner     VARCHAR(200)    DEFAULT NULL                 COMMENT '晚餐地点',
    budget_day      DECIMAL(10,2)   DEFAULT NULL                 COMMENT '当日预算',
    notes           TEXT            DEFAULT NULL                 COMMENT '当日备注/提醒',
    created_at      DATETIME(3)     NOT NULL                     COMMENT '创建时间',
    updated_at      DATETIME(3)     NOT NULL                     COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_day_uuid  (uuid),
    INDEX      idx_day_ref  (ref_uuid, ref_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日行程主表';


-- ------------------------------------------------------------
-- 景点/打卡点表（itinerary_spots）
--
-- category: 0=景点 1=餐厅/美食 2=购物 3=娱乐/活动 4=交通中转 5=其他
-- ------------------------------------------------------------
CREATE TABLE itinerary_spots (
    id               BIGINT         NOT NULL AUTO_INCREMENT      COMMENT '自增主键',
    uuid             VARCHAR(32)    NOT NULL                     COMMENT '对外业务 ID',
    day_uuid         VARCHAR(32)    NOT NULL                     COMMENT '所属 itinerary_days.uuid',
    name             VARCHAR(100)   NOT NULL                     COMMENT '景点/地点名称',
    address          VARCHAR(300)   DEFAULT NULL                 COMMENT '详细地址',
    category         TINYINT        NOT NULL DEFAULT 0           COMMENT '类别：0=景点 1=餐厅 2=购物 3=娱乐 4=中转 5=其他',
    sort_order       INT            NOT NULL DEFAULT 0           COMMENT '自定义排序（升序）',
    duration_minutes INT            DEFAULT NULL                 COMMENT '预计停留时长（分钟）',
    notes            VARCHAR(500)   DEFAULT NULL                 COMMENT '备注',
    created_at       DATETIME(3)    NOT NULL                     COMMENT '创建时间',
    updated_at       DATETIME(3)    NOT NULL                     COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uk_spot_uuid (uuid),
    INDEX      idx_spot_day (day_uuid, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日景点/打卡点表';


SET FOREIGN_KEY_CHECKS = 1;
