package com.vago.travel.model.dto;

import jakarta.validation.constraints.Size;
import lombok.Data;

import java.time.LocalDate;

@Data
public class TripUpdateDTO {

    @Size(max = 100, message = "标题最长 100 个字符")
    private String title;

    @Size(max = 200, message = "地点描述最长 200 个字符")
    private String destination;

    private LocalDate startDate;

    private LocalDate endDate;

    private String coverImageKey;

    /** 行程状态：1=计划中 2=已完成 3=已取消 */
    private Integer status;
}
