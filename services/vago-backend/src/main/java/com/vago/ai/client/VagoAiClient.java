package com.vago.ai.client;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.vago.ai.model.dto.AiChatMessageDTO;
import com.vago.ai.model.vo.AiChatResponseVO;
import com.vago.ai.model.vo.AiSourceCitationVO;
import lombok.Builder;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.stream.Collectors;

/**
 * vago-ai（Python FastAPI）HTTP 客户端。
 *
 * <p>封装所有对 Python 侧的 REST 调用，调用方无需关心 HTTP 细节。
 * 使用 WebClient 实现，同时支持阻塞调用（ingest / delete / chat）和响应式流（chatStream）。
 *
 * <p>内部 Request/Response 模型（仅限此类使用）定义为静态内部类，
 * 与 snake_case 的 Python API 字段通过 @JsonProperty 映射。
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
     * @param guideUuid   攻略 UUID（用作 Qdrant article_id）
     * @param userUuid    归属用户 UUID（用于命名空间隔离）
     * @param title       攻略标题
     * @param content     攻略正文（raw_content）
     * @param destination 目的地（若非空则作为预标注传入）
     * @return Python 返回的入库结果
     */
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
     * @param guideUuid 攻略 UUID
     * @param userUuid  归属用户 UUID（安全校验）
     */
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

    // ── 非流式对话 ─────────────────────────────────────────────────────────────

    /**
     * 非流式 AI 对话：阻塞等待 Agent 完整回答后返回。
     *
     * <p>对应 Python 接口：POST /api/v1/chat
     *
     * @param messages 完整对话历史（含当前轮用户消息）
     * @param userUuid 当前用户 UUID（用于 RAG 命名空间检索）
     * @return 包含回答文本和引用来源的 VO
     */
    public AiChatResponseVO chat(List<AiChatMessageDTO> messages, String userUuid) {
        PythonChatRequest body = buildChatRequest(messages, userUuid);

        try {
            PythonChatResponse resp = webClient.post()
                    .uri("/api/v1/chat")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(PythonChatResponse.class)
                    .block();

            if (resp == null) {
                throw new RuntimeException("vago-ai 返回空响应");
            }
            // 把PythonChatResponse封装为AiSourceCitationVO
            List<AiSourceCitationVO> sources = resp.getSources() == null
                    ? List.of()
                    : resp.getSources().stream()
                            .map(s -> AiSourceCitationVO.builder()
                                    .articleId(s.getArticleId())
                                    .title(s.getTitle())
                                    .chunkText(s.getChunkText())
                                    .score(s.getScore())
                                    .build())
                            // 重新打包为List
                            .collect(Collectors.toList());

            return AiChatResponseVO.builder()
                    .answer(resp.getAnswer())
                    .sources(sources)
                    .model(resp.getModel())
                    .build();

        } catch (WebClientResponseException e) {
            log.error("[VagoAiClient] chat 失败 status={}", e.getStatusCode());
            throw new RuntimeException("vago-ai chat 调用失败: " + e.getMessage(), e);
        }
    }

    // ── 流式对话（SSE） ────────────────────────────────────────────────────────

    /**
     * 流式 AI 对话：返回 SSE 事件 Flux，由 AiController 代理给前端。
     *
     * <p>对应 Python 接口：POST /api/v1/chat/stream
     * <p>Flux 懒加载，在 AiController 订阅时才真正发起 HTTP 请求。
     *
     * @param messages 完整对话历史
     * @param userUuid 当前用户 UUID
     * @return SSE 事件流（data 字段为 JSON 字符串）
     */
    public Flux<ServerSentEvent<String>> chatStream(List<AiChatMessageDTO> messages, String userUuid) {
        PythonChatRequest body = buildChatRequest(messages, userUuid);
        // Flux：异步流式数据的响应管道
        return webClient.post()
                .uri("/api/v1/chat/stream")
                .bodyValue(body)
                .retrieve()
                // 创建一个 ParameterizedTypeReference(参数化类型引用) 的匿名子类，解决泛型擦除问题
                // 在运行期，WebClient 可以通过反射（getGenericSuperclass()）逆向解剖这个子类，越过泛型擦除的封锁，捕获到原本无法获取的 ServerSentEvent<String> 的完整类型信息。
                // 知道精准类型后，Jackson 就能完美地将 Python 吐出来的 SSE 字符串流逐字装填进 ServerSentEvent<String> 中
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {});
    }

    // ── 工具方法 ───────────────────────────────────────────────────────────────

    private PythonChatRequest buildChatRequest(List<AiChatMessageDTO> messages, String userUuid) {
        List<PythonChatMessage> pyMessages = messages.stream()
                .map(m -> new PythonChatMessage(m.getRole(), m.getContent()))
                .collect(Collectors.toList());
        return PythonChatRequest.builder()
                .userUuid(userUuid)
                .messages(pyMessages)
                .useRag(true)
                .topK(6)
                .scoreThreshold(0.55)
                .build();
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

    /** POST /api/v1/chat 及 /chat/stream 请求体 */
    @Data
    @Builder
    public static class PythonChatRequest {
        @JsonProperty("user_uuid")        private String userUuid;
        private List<PythonChatMessage>   messages;
        @JsonProperty("use_rag")          private boolean useRag;
        @JsonProperty("top_k")            private int topK;
        @JsonProperty("score_threshold")  private double scoreThreshold;
    }

    /** 对话消息（role + content） */
    @Data
    public static class PythonChatMessage {
        private String role;
        private String content;
        public PythonChatMessage(String role, String content) {
            this.role = role;
            this.content = content;
        }
    }

    /** POST /api/v1/chat 响应体 */
    @Data
    public static class PythonChatResponse {
        private String answer;
        private List<PythonSourceCitation> sources;
        private String model;
    }

    /** 单条攻略来源引用 */
    @Data
    public static class PythonSourceCitation {
        @JsonProperty("article_id") private String articleId;
        private String title;
        @JsonProperty("chunk_text") private String chunkText;
        private Double score;
    }
}
