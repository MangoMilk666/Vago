package com.vago.interceptor;

import cn.hutool.crypto.digest.DigestUtil;
import com.vago.constant.JwtClaimsConstant;
import com.vago.context.BaseContext;
import com.vago.properties.JwtProperties;
import com.vago.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * JWT 令牌校验拦截器
 * 校验顺序：Token 存在 → 签名合法 → 未在 Redis 黑名单 → 写入 ThreadLocal
 */
@Component
@Slf4j
public class JwtTokenUserInterceptor implements HandlerInterceptor {

    /** Token 黑名单 Redis Key 前缀，与 UserServiceImpl 保持一致 */
    private static final String KEY_TOKEN_BL = "vago:token:bl:%s";

    @Autowired
    private JwtProperties jwtProperties;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @Override
    public boolean preHandle(HttpServletRequest request,
                             HttpServletResponse response,
                             Object handler) throws Exception {
        // 只拦截 Controller 方法，静态资源直接放行
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }

        // 1. 从请求头获取令牌
        String token = request.getHeader(jwtProperties.getTokenName());
        if (token == null || token.isBlank()) {
            log.warn("请求头中未携带 Token");
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return false;
        }

        // 2. 校验 JWT 签名 & 过期时间
        Claims claims;
        try {
            claims = JwtUtil.parseJWT(jwtProperties.getSecretKey(), token);
        } catch (Exception ex) {
            log.warn("JWT 校验失败: {}", ex.getMessage());
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return false;
        }

        // 3. 检查 Token 是否已在黑名单（主动退出登录后加入）
        String blKey = String.format(KEY_TOKEN_BL, DigestUtil.md5Hex(token));
        if (Boolean.TRUE.equals(redisTemplate.hasKey(blKey))) {
            log.warn("Token 已在黑名单，拒绝请求");
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return false;
        }

        // 4. 将用户 UUID 存入 ThreadLocal，供 Service 层使用
        String userUuid = claims.get(JwtClaimsConstant.USER_UUID, String.class);
        log.debug("JWT 通过，当前用户 uuid={}", userUuid);
        BaseContext.setCurrentUuid(userUuid);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        // 请求结束后清理 ThreadLocal，防止内存泄漏
        BaseContext.removeCurrentUuid();
    }
}
