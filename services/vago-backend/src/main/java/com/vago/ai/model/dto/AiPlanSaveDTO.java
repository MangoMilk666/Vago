package com.vago.ai.model.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
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
 *
 * <p>Python 端 structuredPlan 通过 Pydantic model_dump() 输出 snake_case 字段名，
 * 因此所有含下划线的字段均需 @JsonProperty 映射。
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
    // 添加 `@JsonProperty` 注解，显式告知 Jackson 字段映射关系
    @JsonProperty("start_date")
    private String startDate;

    /** 返回日期 YYYY-MM-DD，草稿可为空，行程必填 */
    @JsonProperty("end_date")
    private String endDate;

    private BigDecimal budget;

    @JsonProperty("budget_currency")
    private String budgetCurrency;

    @NotEmpty(message = "每日行程不能为空")
    @Valid
    private List<AiDayDTO> days;

    // ── 嵌套 DTO ─────────────────────────────────────────────────────────────

    @Data
    public static class AiDayDTO {
        @JsonProperty("day_index")
        private int dayIndex;

        @JsonProperty("day_date")
        private String dayDate;          // nullable, YYYY-MM-DD

        private String transportation;
        private String accommodation;

        @JsonProperty("meal_breakfast")
        private String mealBreakfast;

        @JsonProperty("meal_lunch")
        private String mealLunch;

        @JsonProperty("meal_dinner")
        private String mealDinner;

        @JsonProperty("budget_day")
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

        @JsonProperty("sort_order")
        private Integer sortOrder;

        @JsonProperty("duration_minutes")
        private Integer durationMinutes;

        private String notes;
    }
}
