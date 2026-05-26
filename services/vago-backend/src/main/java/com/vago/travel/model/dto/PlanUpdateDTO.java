package com.vago.travel.model.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;

@Data
public class PlanUpdateDTO {

    @Size(max = 100, message = "标题最长 100 个字符")
    private String title;

    @Size(max = 200, message = "地点描述最长 200 个字符")
    private String destination;

    private LocalDate startDate;

    private LocalDate endDate;

    @DecimalMin(value = "0", message = "预算金额不能为负数")
    private BigDecimal budget;

    private String budgetCurrency;

    @Size(max = 2000, message = "备注最长 2000 个字符")
    private String notes;
}
