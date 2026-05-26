package com.vago.user.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 用户-第三方登录绑定实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserOauthBinding implements Serializable {

    private Long id;

    private Long userId;

    /** 登录方：wechat / apple */
    private String provider;

    private String openId;

    /** 最新 Access Token（加密存储） */
    private String accessToken;

    private LocalDateTime expiresAt;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
