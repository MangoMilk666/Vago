package com.vago.utils;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Map;

/**
 * JWT 工具类（基于 JJWT 0.12.x API）
 */
public class JwtUtil {

    /**
     * 生成 JWT
     *
     * @param secretKey jwt 秘钥
     * @param ttlMillis jwt 过期时间（毫秒）
     * @param claims    自定义 payload
     */
    public static String createJWT(String secretKey, long ttlMillis, Map<String, Object> claims) {
        SecretKey key = Keys.hmacShaKeyFor(secretKey.getBytes(StandardCharsets.UTF_8));
        Date exp = new Date(System.currentTimeMillis() + ttlMillis);

        return Jwts.builder()
                .claims(claims)
                .expiration(exp)
                .signWith(key)
                .compact();
    }

    /**
     * 解析 JWT，返回 Claims；令牌非法或过期时抛出异常
     *
     * @param secretKey jwt 秘钥
     * @param token     待解析的令牌
     */
    public static Claims parseJWT(String secretKey, String token) {
        SecretKey key = Keys.hmacShaKeyFor(secretKey.getBytes(StandardCharsets.UTF_8));

        return Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
