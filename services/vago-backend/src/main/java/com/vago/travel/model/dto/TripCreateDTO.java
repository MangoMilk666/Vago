package com.vago.travel.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.time.LocalDate;

@Data
public class TripCreateDTO {

    @NotBlank(message = "行程标题不能为空")
    @Size(max = 100, message = "标题最长 100 个字符")
    private String title;

    @Size(max = 200, message = "地点描述最长 200 个字符")
    private String destination;

    @NotNull(message = "出发日期不能为空")
    private LocalDate startDate;

    @NotNull(message = "返回日期不能为空")
    private LocalDate endDate;

    /** 封面图 OSS Key（可选） */
    private String coverImageKey;
}
