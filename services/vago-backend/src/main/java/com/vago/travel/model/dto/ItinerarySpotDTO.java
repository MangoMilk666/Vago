package com.vago.travel.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class ItinerarySpotDTO {

    /** 新增时为 null；更新/排序时传现有 uuid */
    private String uuid;

    @NotBlank(message = "景点名称不能为空")
    @Size(max = 100, message = "景点名称最长 100 字符")
    private String name;

    @Size(max = 300, message = "地址最长 300 字符")
    private String address;

    /**
     * 类别：0=景点 1=餐厅/美食 2=购物 3=娱乐/活动 4=交通中转 5=其他
     * 不传时默认 0
     */
    private Integer category;

    /** 排序值（客户端维护，升序）*/
    private Integer sortOrder;

    /** 预计停留时长（分钟）*/
    private Integer durationMinutes;

    @Size(max = 500, message = "备注最长 500 字符")
    private String notes;
}
