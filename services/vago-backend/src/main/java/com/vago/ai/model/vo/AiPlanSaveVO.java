package com.vago.ai.model.vo;

import lombok.Builder;
import lombok.Data;

/**
 * AI 结构化行程保存结果。
 */
@Data
@Builder
public class AiPlanSaveVO {
    /** 创建的 plan/trip UUID */
    private String uuid;
    /** 类型标识："plan" 或 "trip" */
    private String type;
}
