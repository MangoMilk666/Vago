package com.vago.travel.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 旅行计划实体（草稿态，可转为正式行程）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Plan implements Serializable {

    /** DB 自增主键 */
    private Long id;

    /** 对外业务 ID */
    private String uuid;

    /** 归属用户 UUID */
    private String userUuid;

    /** 计划标题 */
    private String title;

    /** 目标地点 */
    private String destination;

    /** 计划出发日期（可空，尚未确定时留空） */
    private LocalDate startDate;

    /** 计划返回日期（可空） */
    private LocalDate endDate;

    /** 费用预算 */
    private BigDecimal budget;

    /** 预算货币（默认 CNY） */
    private String budgetCurrency;

    /** 备注/草稿内容 */
    private String notes;

    /** 转换后的正式行程 UUID（为 NULL 表示尚未转换） */
    private String convertedTripUuid;

    /**
     * 计划状态
     * <ul>
     *   <li>0 = 草稿</li>
     *   <li>1 = 已转为正式行程</li>
     * </ul>
     */
    private Integer status;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    /** 软删除时间 */
    private LocalDateTime deletedAt;
}
