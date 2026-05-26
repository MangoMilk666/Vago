package com.vago.travel.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PlanVO {

    private String uuid;
    private String title;
    private String destination;
    private LocalDate startDate;
    private LocalDate endDate;
    private BigDecimal budget;
    private String budgetCurrency;
    private String notes;

    /** 已转换的正式行程 UUID（null 表示尚未转换） */
    private String convertedTripUuid;

    /** 0=草稿 1=已转为正式行程 */
    private Integer status;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
