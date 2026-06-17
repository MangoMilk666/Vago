package com.vago.ai.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.retry.annotation.EnableRetry;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * AI 客户端配置。
 *
 * <p>注册面向 vago-ai（Python FastAPI）的 WebClient Bean，并开启 Spring @Async 和 @Retryable 支持。
 * 服务地址通过配置项 {@code vago.ai.base-url} 注入，默认指向本地开发环境。
 *
 * <p>{@code @EnableAsync} 和 {@code @EnableRetry} 放在此处，保证 AiServiceImpl 中的
 * {@code @Async} 和 VagoAiClient 中的 {@code @Retryable} 在 Spring 容器启动后即可被代理执行。
 */
@Configuration
@EnableAsync
@EnableRetry
public class AiClientConfig {

    /** vago-ai 服务基础地址，由 application.yml 注入 */
    @Value("${vago.ai.base-url:http://localhost:8000}")
    private String aiBaseUrl;

    /**
     * 创建并返回专用于调用 vago-ai 的 WebClient 单例 Bean。
     *
     * <p>配置说明：
     * <ul>
     *   <li>baseUrl — Python FastAPI 服务地址</li>
     *   <li>defaultHeader Content-Type — 统一使用 JSON</li>
     *   <li>maxInMemorySize — 非流式响应最大缓冲 16 MB，防止大模型回答超限</li>
     * </ul>
     *
     * @return 配置好的 WebClient 实例
     */
    @Bean("vagoAiWebClient")
    public WebClient vagoAiWebClient() {
        return WebClient.builder()
                .baseUrl(aiBaseUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
    }
}
