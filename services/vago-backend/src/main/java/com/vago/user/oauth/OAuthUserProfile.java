package com.vago.user.oauth;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 标准化后的第三方用户资料。
 */
@Data
@Builder
public class OAuthUserProfile {

    private String provider;

    private String openId;

    private String email;

    private String nickname;

    private String avatarUrl;

    private String accessToken;

    private LocalDateTime expiresAt;
}
