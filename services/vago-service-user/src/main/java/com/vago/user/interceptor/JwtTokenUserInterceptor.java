package com.vago.user.interceptor;

import com.vago.user.constant.JwtClaimsConstant;
import com.vago.user.context.BaseContext;
import com.vago.user.properties.JwtProperties;
import com.vago.user.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * JWT 令牌校验拦截器（C 端用户）
 */
@Component
@Slf4j
public class JwtTokenUserInterceptor implements HandlerInterceptor {

    @Autowired
    private JwtProperties jwtProperties;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        // 只拦截 Controller 方法，静态资源直接放行
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }

        // 1. 从请求头中获取令牌
        String token = request.getHeader(jwtProperties.getTokenName());

        // 2. 校验令牌
        try {
            log.info("jwt 校验用户令牌: {}", token);
            Claims claims = JwtUtil.parseJWT(jwtProperties.getSecretKey(), token);
            String userUuid = claims.get(JwtClaimsConstant.USER_UUID, String.class);
            log.info("当前用户 uuid: {}", userUuid);

            // 3. 将用户 uuid 存入 ThreadLocal，供后续 service 层使用
            BaseContext.setCurrentUuid(userUuid);
            return true;
        } catch (Exception ex) {
            log.warn("jwt 校验失败: {}", ex.getMessage());
            // 4. 校验失败，返回 401
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return false;
        }
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        // 请求结束后清理 ThreadLocal，防止内存泄漏
        BaseContext.removeCurrentUuid();
    }

}
