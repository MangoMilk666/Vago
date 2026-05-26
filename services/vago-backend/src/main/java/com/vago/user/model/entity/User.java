package com.vago.user.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 用户信息实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class User implements Serializable {

    /** DB 自增主键 */
    private Long id;

    /** 对外业务 ID（UUID） */
    private String uuid;

    private String phone;

    private String email;

    private String nickname;

    private String avatarOssKey;

    /** 订阅套餐：0=免费版 1=付费版 */
    private Integer planType;

    /** 攻略库配额上限 */
    private Integer articleQuota;

    /** 今日 AI 调用次数（日终归档，实时计数在 Redis） */
    private Integer aiCallsToday;

    /** 账户状态：1=正常 2=封禁 3=注销中 */
    private Integer status;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;

    /** 软删除时间，NULL 表示未删除 */
    private LocalDateTime deletedAt;
}
