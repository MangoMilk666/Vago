package com.vago.travel.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ItinerarySpotVO {

    private String uuid;
    private String name;
    private String address;

    /** 0=景点 1=餐厅/美食 2=购物 3=娱乐/活动 4=交通中转 5=其他 */
    private Integer category;

    private Integer sortOrder;

    /** 预计停留时长（分钟） */
    private Integer durationMinutes;

    private String notes;
}
