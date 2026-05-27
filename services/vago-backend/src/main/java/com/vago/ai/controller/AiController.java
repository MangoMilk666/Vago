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
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.publisher.Flux;

import java.io.IOException;
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
    public SseEmitter chatStream(@Valid @RequestBody AiChatRequestDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        validateLastMessageIsUser(dto);

        log.info("[AiController] 流式对话 user={} messages={}", userUuid, dto.getMessages().size());

        // 5 分钟超时（大模型生成可能较慢，留足裕量）
        SseEmitter emitter = new SseEmitter(300_000L);
        // 返回Flux，异步流式数据的响应管道
        Flux<ServerSentEvent<String>> flux = aiService.chatStream(dto, userUuid);
        /**
         * 调用 .subscribe() 的瞬间，对系统下达了三个核心指令：
         *     1.正式向远端 Python AI 服务发起 HTTP POST 请求，建立长连接。
         *     2.在 Java 的内存里安插好三个监听回调，分别监听“数据流过”、“流发生报错”、“流顺利结束”。
         *     3.彻底释放当前 Tomcat 线程：这段 .subscribe() 代码执行只需 1毫秒。执行完后，主线程立刻带着创建好的 SseEmitter 对象返回给前端。
         *     此时，Tomcat 线程被安全回收，而数据转发的逻辑全部托管给了后台的异步线程。
         */
        flux.subscribe(
                // 1. onNext 监听器（只要有新字吐出来，就执行这里）
            event -> {
                // Python 端 SSE data 字段为 JSON 字符串，直接透传给前端
                String data = event.data() != null ? event.data() : "";
                try {
                    emitter.send(SseEmitter.event().data(data));
                } catch (IOException e) {
                    log.warn("[AiController] SSE send 失败 user={}: {}", userUuid, e.getMessage());
                    emitter.completeWithError(e);
                }
            },
                // 2. onError 监听器（只要中途断网或AI报错，就执行这里）
            error -> {
                log.error("[AiController] 流式生成异常 user={} error={}", userUuid, error.getMessage(), error);
                try {
                    // 向前端推送错误事件再关闭流，避免前端收到空流
                    String errPayload = "{\"type\":\"error\",\"message\":\"AI 服务暂时不可用，请稍后重试\"}";
                    emitter.send(SseEmitter.event().data(errPayload));
                } catch (IOException ignored) {
                    // 推送错误事件失败时直接终止
                }
                emitter.completeWithError(error);
            },
            // 3. onComplete 监听器（Python 吐完，结束）
            emitter::complete
        );

        return emitter;
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
