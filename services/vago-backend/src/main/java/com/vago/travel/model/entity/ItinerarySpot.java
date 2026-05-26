package com.vago.travel.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 每日景点 / 打卡点实体
 *
 * <p>category 枚举：
 * <ul>
 *   <li>0 = 景点</li>
 *   <li>1 = 餐厅 / 美食</li>
 *   <li>2 = 购物</li>
 *   <li>3 = 娱乐 / 活动</li>
 *   <li>4 = 交通中转</li>
 *   <li>5 = 其他</li>
 * </ul>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ItinerarySpot implements Serializable {

    private Long id;

    /** 对外业务 ID */
    private String uuid;

    /** 所属 itinerary_days.uuid */
    private String dayUuid;

    /** 景点名称 */
    private String name;

    /** 地址 */
    private String address;

    /** 类别（0~5） */
    private Integer category;

    /** 排序值（升序，越小越靠前） */
    private Integer sortOrder;

    /** 预计停留时长（分钟） */
    private Integer durationMinutes;

    /** 备注 */
    private String notes;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
