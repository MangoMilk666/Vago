package com.vago.travel.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ItineraryDayVO {

    private String uuid;

    /** 当日日期 */
    private LocalDate dayDate;

    /** 第几天（1 起始） */
    private Integer dayIndex;

    /** 出行方式 */
    private String transportation;

    /** 住宿地点 */
    private String accommodation;

    /** 早餐地点 */
    private String mealBreakfast;

    /** 午餐地点 */
    private String mealLunch;

    /** 晚餐地点 */
    private String mealDinner;

    /** 当日预算 */
    private BigDecimal budgetDay;

    /** 当日备注 */
    private String notes;

    /** 景点列表（按 sortOrder 升序） */
    private List<ItinerarySpotVO> spots;
}
