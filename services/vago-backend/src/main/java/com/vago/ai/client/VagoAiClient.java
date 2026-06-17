package com.vago.ai.client;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Recover;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.List;

/**
 * vago-ai（Python FastAPI）HTTP 客户端。
 *
 * <p>封装 Java 内部调用 Python 的 REST 接口（ingest / delete），
 * 供 AiServiceImpl @Async 线程使用。
 *
 * <p>AI 对话接口（chat / chatStream）已重构为前端直连 Python，
 * Java 不再代理 SSE 流，对应方法已从本类移除。
 */
@Component
@Slf4j
public class VagoAiClient {

    private final WebClient webClient;
    // 依赖注入（构造器注入）
    public VagoAiClient(@Qualifier("vagoAiWebClient") WebClient webClient) {
        this.webClient = webClient;
    }

    // ── 攻略向量入库 ───────────────────────────────────────────────────────────

    /**
     * 将攻略内容提交至 vago-ai 向量化管道（同步阻塞，供 @Async 线程调用）。
     *
     * <p>对应 Python 接口：POST /api/v1/articles/ingest
     *
     * <p>使用 {@link Retryable} 自动重试：网络抖动 / Python 重启等瞬时故障时，
     * 最多重试 2 次（共 3 次尝试），每次间隔递增 1 秒。
     * 若所有重试均失败，由 {@link Recover} 方法返回降级响应。
     * Backoff 参数定义了重试的节奏和频率，delay - 首次重试前的固定等待时间， multiplier - 延迟倍率（指数退避）
     *
     * @param guideUuid   攻略 UUID（用作 Qdrant article_id）
     * @param userUuid    归属用户 UUID（用于命名空间隔离）
     * @param title       攻略标题
     * @param content     攻略正文（raw_content）
     * @param destination 目的地（若非空则作为预标注传入）
     * @return Python 返回的入库结果；全部重试失败时返回降级结果
     */
    @Retryable(
        retryFor = {WebClientRequestException.class, WebClientResponseException.class},
        maxAttempts = 3,
        backoff = @Backoff(delay = 1000, multiplier = 1.5)
    )
    public IngestResponse ingestGuide(String guideUuid, String userUuid,
                                      String title, String content, String destination) {
        // 组装post请求体
        IngestRequest body = IngestRequest.builder()
                .articleId(guideUuid)
                .userUuid(userUuid)
                .title(title)
                .rawContent(content)
                .destinations(destination != null && !destination.isBlank()
                        ? List.of(destination) : null)
                .build();

        try {
            IngestResponse resp = webClient.post()
                    .uri("/api/v1/articles/ingest")
                    .bodyValue(body)
                    // 接收响应
                    .retrieve()
                    .bodyToMono(IngestResponse.class)
                    // 阻塞当前线程
                    // 采用传统 Java 调用微服务（比如主服务去调用 Python AI 向量入库接口）标准过渡期写法
                    .block();
            return resp != null ? resp : new IngestResponse();
        } catch (WebClientResponseException e) {
            log.error("[VagoAiClient] ingest 失败 status={} body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new RuntimeException("vago-ai ingest 调用失败: " + e.getMessage(), e);
        }
    }

    // ── 攻略向量删除 ───────────────────────────────────────────────────────────

    /**
     * 从 Qdrant 删除指定攻略的全部向量数据（同步阻塞，供 @Async 线程调用）。
     *
     * <p>对应 Python 接口：DELETE /api/v1/articles/{articleId}?user_uuid={userUuid}
     *
     * <p>同样支持重试：网络瞬时故障时最多重试 2 次。
     * 全部重试失败后，由 {@link Recover} 方法降级处理（仅日志告警）。
     *
     * @param guideUuid 攻略 UUID
     * @param userUuid  归属用户 UUID（安全校验）
     */
    @Retryable(
        retryFor = {WebClientRequestException.class, WebClientResponseException.class},
        maxAttempts = 3,
        backoff = @Backoff(delay = 1000, multiplier = 1.5)
    )
    public void deleteGuide(String guideUuid, String userUuid) {
        try {
            webClient.delete()
                    .uri(uriBuilder -> uriBuilder
                            .path("/api/v1/articles/{articleId}")
                            .queryParam("user_uuid", userUuid)
                            .build(guideUuid))
                    .retrieve()
                    .toBodilessEntity()
                    .block();
        } catch (WebClientResponseException e) {
            log.error("[VagoAiClient] delete 失败 status={} guide={}", e.getStatusCode(), guideUuid);
            throw new RuntimeException("vago-ai delete 调用失败: " + e.getMessage(), e);
        }
    }

    // ── @Recover 降级方法 ──────────────────────────────────────────────────────

    /**
     * ingestGuide 全部重试失败后的降级处理。
     * 返回一个标记为 FAILED 的 IngestResponse，避免异常传播到 @Async 调用方。
     */
    @Recover
    public IngestResponse ingestGuideFallback(Exception e, String guideUuid, String userUuid,
                                               String title, String content, String destination) {
        log.error("[VagoAiClient] ingest 重试全部失败 guide={} error={}", guideUuid, e.getMessage());
        IngestResponse fallback = new IngestResponse();
        fallback.setArticleId(guideUuid);
        fallback.setStatus("FAILED");
        fallback.setChunkCount(0);
        fallback.setMessage("向量化服务暂时不可用，请稍后重试：" + e.getMessage());
        return fallback;
    }

    /**
     * deleteGuide 全部重试失败后的降级处理。
     * 仅记录日志告警，不抛出异常（删除失败不影响主流程）。
     */
    @Recover
    public void deleteGuideFallback(Exception e, String guideUuid, String userUuid) {
        log.error("[VagoAiClient] delete 重试全部失败 guide={} error={}，" +
                "请手动检查 Qdrant 中是否有残留向量数据", guideUuid, e.getMessage());
    }

    // ── Python API 内部 Request / Response 模型（仅限本类使用）───────────────

    /** POST /api/v1/articles/ingest 请求体 */
    @Data
    @Builder
    public static class IngestRequest {
        @JsonProperty("article_id")  private String articleId;
        @JsonProperty("user_uuid")   private String userUuid;
        private String title;
        @JsonProperty("source_url")  private String sourceUrl;
        @JsonProperty("raw_content") private String rawContent;
        private List<String> destinations;
    }

    /** POST /api/v1/articles/ingest 响应体（仅取 status / chunkCount / message） */
    @Data
    public static class IngestResponse {
        @JsonProperty("article_id")  private String articleId;
        private String status;
        @JsonProperty("chunk_count") private int chunkCount;
        private String message;
    }

}
