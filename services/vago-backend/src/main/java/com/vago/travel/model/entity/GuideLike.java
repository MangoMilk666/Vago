package com.vago.travel.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 攻略点赞关系表实体。
 * 点赞以 Redis 为实时权威存储，guide_likes 表由 LikeFlushTask 每 5 分钟从 Redis 异步刷入，
 * 作为持久化兜底。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GuideLike implements Serializable {

    /** 攻略 UUID */
    private String guideUuid;

    /** 用户 UUID */
    private String userUuid;

    /** 点赞时间 */
    private LocalDateTime createdAt;
}
