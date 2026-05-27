package com.vago.ai.model.vo;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * AI 非流式对话响应 VO（Java → 前端）。
 *
 * <p>流式对话（SSE）直接代理 Python 的 SSE 事件，无需此 VO。
 */
@Data
@Builder
public class AiChatResponseVO {

    /** 模型生成的回答文本 */
    private String answer;

    /**
     * 引用的攻略来源列表。
     * 若 Agent 未检索攻略库（非旅行问题或攻略库为空），此列表为空。
     */
    private List<AiSourceCitationVO> sources;

    /** 实际使用的大模型名称（如 qwen-plus / gpt-4o-mini） */
    private String model;
}
