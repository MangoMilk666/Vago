package com.vago.ai.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * AI 对话单条消息 DTO。
 *
 * <p>兼容 OpenAI Chat Completions 消息格式：
 * role 限定为 user / assistant / system，content 不可为空。
 */
@Data
public class AiChatMessageDTO {

    /** 消息角色：user=用户输入，assistant=模型回复，system=系统提示 */
    @NotBlank(message = "消息 role 不能为空")
    @Pattern(regexp = "user|assistant|system", message = "role 仅允许 user / assistant / system")
    private String role;

    /** 消息正文 */
    @NotBlank(message = "消息内容不能为空")
    private String content;
}
