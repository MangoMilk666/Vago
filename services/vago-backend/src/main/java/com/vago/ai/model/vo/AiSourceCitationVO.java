package com.vago.ai.model.vo;

import lombok.Builder;
import lombok.Data;

/**
 * RAG 检索命中的攻略来源 VO。
 *
 * <p>随 AI 回答一同返回，前端可据此展示"回答依据"引用卡片。
 */
@Data
@Builder
public class AiSourceCitationVO {

    /** 攻略 UUID（与 Guide.uuid 对应） */
    private String articleId;

    /** 攻略标题 */
    private String title;

    /** 命中的文本块摘要（前 300 字） */
    private String chunkText;

    /** 与查询的余弦相似度得分，范围 [0, 1] */
    private Double score;
}
