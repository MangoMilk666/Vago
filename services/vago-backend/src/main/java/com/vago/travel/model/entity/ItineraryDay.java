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
 * 每日行程主体实体
 *
 * <p>通过 refUuid + refType 同时服务 Trip 和 Plan，避免重复建表。
 * <ul>
 *   <li>refType = 1 → trips.uuid</li>
 *   <li>refType = 2 → plans.uuid</li>
 * </ul>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ItineraryDay implements Serializable {
    // 归属类型，1-行程，2-计划
    public static final int REF_TYPE_TRIP = 1;
    public static final int REF_TYPE_PLAN = 2;

    private Long id;

    /** 对外业务 ID */
    private String uuid;

    /** 所属行程/计划的 UUID */
    private String refUuid;

    /** 归属类型：1=行程 2=计划 */
    private Integer refType;

    /** 当日日期 */
    private LocalDate dayDate;

    /** 第几天（1 起始） */
    private Integer dayIndex;

    /** 出行方式（飞机 / 高铁 / 自驾 / 轮渡 / 徒步…） */
    private String transportation;

    /** 住宿地点 / 酒店名称 */
    private String accommodation;

    /** 早餐地点 */
    private String mealBreakfast;

    /** 午餐地点 */
    private String mealLunch;

    /** 晚餐地点 */
    private String mealDinner;

    /** 当日预算 */
    private BigDecimal budgetDay;

    /** 当日备注 / 提醒事项 */
    private String notes;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
