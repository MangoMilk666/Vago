package com.vago.travel.model.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;

@Data
public class PlanCreateDTO {

    @NotBlank(message = "计划标题不能为空")
    @Size(max = 100, message = "标题最长 100 个字符")
    private String title;

    @Size(max = 200, message = "地点描述最长 200 个字符")
    private String destination;

    /** 计划出发日期（可为空，尚未确定时不填） */
    private LocalDate startDate;

    /** 计划返回日期 */
    private LocalDate endDate;

    @DecimalMin(value = "0", message = "预算金额不能为负数")
    private BigDecimal budget;

    /** 货币单位（默认 CNY） */
    private String budgetCurrency;

    @Size(max = 2000, message = "备注最长 2000 个字符")
    private String notes;
}
