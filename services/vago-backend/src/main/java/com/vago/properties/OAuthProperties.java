package com.vago.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 第三方 OAuth 配置类。
 */
@Component
@ConfigurationProperties(prefix = "vago.oauth")
@Data
public class OAuthProperties {

    private Github github = new Github();

    @Data
    public static class Github {
        private String clientId;
        private String clientSecret;
        private String authorizeUrl = "https://github.com/login/oauth/authorize";
        private String tokenUrl = "https://github.com/login/oauth/access_token";
        private String userUrl = "https://api.github.com/user";
        private String emailsUrl = "https://api.github.com/user/emails";
    }
}
