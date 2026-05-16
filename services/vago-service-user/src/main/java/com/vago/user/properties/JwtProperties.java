package com.vago.user.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 将配置文件中的 vago.jwt.* 封装为 Java 对象
 */
@Component
@ConfigurationProperties(prefix = "vago.jwt")
@Data
public class JwtProperties {

    /** 签名秘钥 */
    private String secretKey;

    /** Access Token 过期时间（毫秒） */
    private long accessTokenTtl;

    /** Refresh Token 过期时间（毫秒） */
    private long refreshTokenTtl;

    /** 请求头中 Token 的字段名，默认 authorization */
    private String tokenName;

}
