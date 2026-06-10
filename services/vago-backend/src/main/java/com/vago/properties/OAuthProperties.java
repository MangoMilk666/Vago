package com.vago.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 第三方 OAuth 配置。
 *
 * <p>配置来源：application.yml / application-*.yml / 系统环境变量。
 * <p>当前 GitHub 配置映射：
 * <pre>
 *   vago.oauth.github.client-id      -> OAuthProperties.Github#clientId
 *   vago.oauth.github.client-secret  -> OAuthProperties.Github#clientSecret
 *   vago.oauth.github.authorize-url  -> OAuthProperties.Github#authorizeUrl
 *   vago.oauth.github.token-url      -> OAuthProperties.Github#tokenUrl
 *   vago.oauth.github.user-url       -> OAuthProperties.Github#userUrl
 *   vago.oauth.github.emails-url     -> OAuthProperties.Github#emailsUrl
 * </pre>
 * <p>安全：不要把 clientSecret 直接写死在可提交的配置文件里，建议用环境变量注入。
 */
@Component
@ConfigurationProperties(prefix = "vago.oauth")
@Data
public class OAuthProperties {

    private Github github = new Github();

    @Data
    public static class Github {
        /** GitHub OAuth App Client ID */
        private String clientId;
        /** GitHub OAuth App Client Secret（敏感信息） */
        private String clientSecret;
        /** GitHub 授权页面地址（前端跳转用；后端通常不直接使用） */
        private String authorizeUrl = "https://github.com/login/oauth/authorize";
        /** GitHub 换码（authCode -> token）接口地址 */
        private String tokenUrl = "https://github.com/login/oauth/access_token";
        /** GitHub 用户信息接口（/user） */
        private String userUrl = "https://api.github.com/user";
        /** GitHub 邮箱列表接口（/user/emails） */
        private String emailsUrl = "https://api.github.com/user/emails";
    }
}
