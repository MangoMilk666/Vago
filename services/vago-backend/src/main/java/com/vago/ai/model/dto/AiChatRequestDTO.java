package com.vago.ai.model.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

/**
 * AI 对话请求 DTO（前端 → Java）。
 *
 * <p>前端负责维护完整对话历史并按序传入，服务端无状态。
 * 最后一条消息必须为 role=user（由 AiController 校验）。
 * user_uuid 由 JWT 拦截器注入，无需客户端传递。
 */
@Data
public class AiChatRequestDTO {

    /**
     * 完整对话历史（含本轮用户消息）。
     * 列表最后一条必须为 role=user 的消息，由 Controller 层校验。
     */
    @NotEmpty(message = "对话消息不能为空")
    @Valid
    private List<AiChatMessageDTO> messages;
}
