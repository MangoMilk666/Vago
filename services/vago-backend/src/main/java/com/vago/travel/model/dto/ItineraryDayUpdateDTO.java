package com.vago.travel.model.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * 更新单日行程 DTO
 *
 * <p>spots 列表采用"全量替换"策略：
 * <ul>
 *   <li>spots 为 null → 不修改景点</li>
 *   <li>spots 为空列表 → 清空当日所有景点</li>
 *   <li>spots 不为空 → 删除旧景点，按顺序重建（sortOrder 由列表下标自动补全）</li>
 * </ul>
 */
@Data
public class ItineraryDayUpdateDTO {

    @Size(max = 200, message = "出行方式描述最长 200 字符")
    private String transportation;

    @Size(max = 300, message = "住宿地点最长 300 字符")
    private String accommodation;

    @Size(max = 200, message = "早餐地点最长 200 字符")
    private String mealBreakfast;

    @Size(max = 200, message = "午餐地点最长 200 字符")
    private String mealLunch;

    @Size(max = 200, message = "晚餐地点最长 200 字符")
    private String mealDinner;

    @DecimalMin(value = "0", message = "预算不能为负数")
    private BigDecimal budgetDay;

    @Size(max = 2000, message = "备注最长 2000 字符")
    private String notes;

    /** 景点列表（全量替换，null 表示不动） */
    @Valid
    private List<ItinerarySpotDTO> spots;
}
