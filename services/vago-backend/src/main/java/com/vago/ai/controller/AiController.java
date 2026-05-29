package com.vago.ai.controller;

import com.vago.ai.model.dto.AiChatMessageDTO;
import com.vago.ai.model.dto.AiChatRequestDTO;
import com.vago.ai.model.vo.AiChatResponseVO;
import com.vago.ai.service.AiService;
import com.vago.common.Result;
import com.vago.common.ResultCode;
import com.vago.context.BaseContext;
import com.vago.exception.BusinessException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import java.util.List;

/**
 * AI 对话控制器。
 *
 * <p>对外暴露两个端点：
 * <ul>
 *   <li>POST /api/v1/ai/chat        — 非流式，等待完整回答后返回 JSON</li>
 *   <li>POST /api/v1/ai/chat/stream — 流式 SSE，实时推送 token（打字机效果）</li>
 * </ul>
 *
 * <p>两个端点均需 JWT 鉴权（由 JwtTokenUserInterceptor 统一处理），
 * user_uuid 从 ThreadLocal（BaseContext）中取得，无需客户端传递。
 *
 * <p>SSE 事件格式（Python vago-ai 原样透传）：
 * <pre>
 *   {"type": "text",      "content": "..."}   — 文本 token
 *   {"type": "searching", "query":   "..."}   — Agent 检索中
 *   {"type": "sources",   "sources": [...]}   — 引用来源
 *   {"type": "error",     "message": "..."}   — 生成错误
 *   data: [DONE]                              — 流结束
 * </pre>
 */
@Tag(name = "AI 对话")
@RestController
@RequestMapping("/api/v1/ai")
@Slf4j
public class AiController {

    @Autowired
    private AiService aiService;

    // ── 非流式对话 ─────────────────────────────────────────────────────────────

    @Operation(
        summary = "AI 对话（非流式）",
        description = "传入完整对话历史，Agent 生成完整回答后一次性返回 JSON。\n\n"
            + "适合后台批量生成场景；实时打字机效果请使用 /chat/stream 接口。\n\n"
            + "消息历史由调用方（前端）维护并完整传入，服务端无状态。"
    )
    @PostMapping("/chat")
    public Result<AiChatResponseVO> chat(@Valid @RequestBody AiChatRequestDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        validateLastMessageIsUser(dto);

        log.info("[AiController] 非流式对话 user={} messages={}", userUuid, dto.getMessages().size());

        try {
            return Result.success(aiService.chat(dto, userUuid));
        } catch (Exception e) {
            log.error("[AiController] 非流式对话失败 user={} error={}", userUuid, e.getMessage(), e);
            throw new BusinessException(ResultCode.AI_SERVICE_UNAVAILABLE);
        }
    }

    // ── 流式对话（SSE） ────────────────────────────────────────────────────────

    @Operation(
        summary = "AI 对话（流式 SSE）",
        description = "以 SSE（Server-Sent Events）格式实时推送 token，适合前端实现打字机效果。\n\n"
            + "前端通过 `fetch` + `ReadableStream` 消费，拼接 type=text 事件的 content 字段。\n\n"
            + "流结束时收到 `data: [DONE]`，前端据此关闭连接。"
    )
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> chatStream(@Valid @RequestBody AiChatRequestDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        validateLastMessageIsUser(dto);

        log.info("[AiController] 流式对话 user={} messages={}", userUuid, dto.getMessages().size());

        // 直接返回 Flux，由 Spring 的响应式 SSE 写入器（ServerSentEventHttpMessageWriter）托管。
        // 与原 SseEmitter + flux.subscribe() 方案相比：
        //   1. 编码正确：ServerSentEventHttpMessageWriter 默认 UTF-8，彻底消除 StringHttpMessageConverter
        //      默认 ISO-8859-1 导致中文变 '?' 的问题；
        //   2. 代码简洁：Spring 自动处理背压、onComplete、连接关闭，无需手动 subscribe；
        //   3. 错误透明：onErrorResume 将异常转为一条 error 事件推送给前端，不丢失错误信息。
        return aiService.chatStream(dto, userUuid)
            .onErrorResume(error -> {
                log.error("[AiController] 流式生成异常 user={} error={}", userUuid, error.getMessage(), error);
                String errPayload = "{\"type\":\"error\",\"message\":\"AI 服务暂时不可用，请稍后重试\"}";
                return Flux.just(ServerSentEvent.<String>builder().data(errPayload).build());
            });
    }

    // ── 私有工具 ───────────────────────────────────────────────────────────────

    /**
     * 校验消息列表最后一条必须为 role=user。
     * Python 侧也有此校验，Java 层提前拦截，避免无效调用消耗 AI 额度。
     *
     * @param dto 待校验的请求体
     * @throws BusinessException PARAM_INVALID — 格式不合法时
     */
    private void validateLastMessageIsUser(AiChatRequestDTO dto) {
        List<AiChatMessageDTO> messages = dto.getMessages();
        if (messages.isEmpty() || !"user".equals(messages.get(messages.size() - 1).getRole())) {
            throw new BusinessException(ResultCode.PARAM_INVALID);
        }
    }
}
