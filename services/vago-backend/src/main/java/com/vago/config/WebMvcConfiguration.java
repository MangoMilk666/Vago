package com.vago.config;

import com.vago.interceptor.JwtTokenUserInterceptor;
import com.vago.json.JacksonObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.web.servlet.config.annotation.AsyncSupportConfigurer;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurationSupport;

import java.util.List;

/**
 * Web 层组件注册
 * - JWT 拦截器
 * - Swagger UI 静态资源
 * - Jackson 日期格式转换器
 * - CORS（开发阶段）
 */
@Configuration
@Slf4j
public class WebMvcConfiguration extends WebMvcConfigurationSupport {

    @Autowired
    private JwtTokenUserInterceptor jwtTokenUserInterceptor;

    /**
     * 注册 JWT 拦截器
     * 新增业务域时，在此追加 excludePathPatterns 或 addPathPatterns 即可
     */
    @Override
    protected void addInterceptors(InterceptorRegistry registry) {
        log.info("注册 JWT 拦截器...");
        registry.addInterceptor(jwtTokenUserInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns(
                        // 用户域：无需鉴权的开放端点
                        "/api/v1/user/sms/send",
                        "/api/v1/user/register",
                        "/api/v1/user/login/phone",
                        "/api/v1/user/login/oauth",
                        "/api/v1/user/token/refresh"
                );
    }

    /** Swagger UI 静态资源（WebMvcConfigurationSupport 会关闭自动映射，需手动注册） */
    @Override
    protected void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/swagger-ui/**")
                .addResourceLocations("classpath:/META-INF/resources/webjars/swagger-ui/");
        registry.addResourceHandler("/v3/api-docs/**")
                .addResourceLocations("classpath:/META-INF/resources/");
        registry.addResourceHandler("/webjars/**")
                .addResourceLocations("classpath:/META-INF/resources/webjars/");
    }

    /** 将自定义 ObjectMapper 注册为首选消息转换器，统一 LocalDateTime 格式 */
    @Override
    protected void extendMessageConverters(List<HttpMessageConverter<?>> converters) {
        MappingJackson2HttpMessageConverter converter = new MappingJackson2HttpMessageConverter();
        converter.setObjectMapper(new JacksonObjectMapper());
        converters.add(0, converter);
    }

    /**
     * 配置 MVC 异步支持：
     * 1. 替换默认 SimpleAsyncTaskExecutor（无池化，高并发下线程耗尽）为 ThreadPoolTaskExecutor。
     * 2. 关闭异步请求超时（-1），防止 Tomcat 默认 10s 超时强制中断 SSE 长连接。
     *    SSE 流式 AI 响应可能持续数十秒，必须禁用超时或设置足够大的值。
     */
    @Override
    protected void configureAsyncSupport(AsyncSupportConfigurer configurer) {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(8);
        executor.setMaxPoolSize(32);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("mvc-async-");
        executor.initialize();
        configurer.setTaskExecutor(executor);
        // -1 表示不超时；SSE 连接由客户端断开或 Flux 完成来终止
        configurer.setDefaultTimeout(-1);
    }

    /** CORS（联调阶段允许本地前端跨域） */
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(
                        "http://localhost:5173",   // Vite Dev Server
                        "http://localhost:3000"    // 备用
                )
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
