package com.vago.ai.model.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * AI 结构化行程保存请求体。
 *
 * <p>前端从 AI 生成的 structuredPlan 中提取数据，
 * 提交至 /api/v1/ai/plans/save-draft 或 /plans/save-trip 端点。
 */
@Data
public class AiPlanSaveDTO {

    @NotBlank(message = "标题不能为空")
    @Size(max = 100)
    private String title;

    @NotBlank(message = "目的地不能为空")
    @Size(max = 200)
    private String destination;

    /** 出发日期 YYYY-MM-DD，草稿可为空，行程必填 */
    private String startDate;

    /** 返回日期 YYYY-MM-DD，草稿可为空，行程必填 */
    private String endDate;

    private BigDecimal budget;

    private String budgetCurrency;

    @NotEmpty(message = "每日行程不能为空")
    @Valid
    private List<AiDayDTO> days;

    // ── 嵌套 DTO ─────────────────────────────────────────────────────────────

    @Data
    public static class AiDayDTO {
        private int dayIndex;
        private String dayDate;          // nullable, YYYY-MM-DD
        private String transportation;
        private String accommodation;
        private String mealBreakfast;
        private String mealLunch;
        private String mealDinner;
        private BigDecimal budgetDay;
        private String notes;
        @Valid
        private List<AiSpotDTO> spots;
    }

    @Data
    public static class AiSpotDTO {
        @NotBlank(message = "景点名称不能为空")
        private String name;
        private String address;
        private Integer category;        // 0-5, default 0
        private Integer sortOrder;
        private Integer durationMinutes;
        private String notes;
    }
}
