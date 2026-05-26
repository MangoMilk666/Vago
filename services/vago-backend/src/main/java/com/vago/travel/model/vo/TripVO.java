package com.vago.travel.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TripVO {

    private String uuid;
    private String title;
    private String destination;
    private String coverImageKey;
    private LocalDate startDate;
    private LocalDate endDate;

    /** 1=计划中 2=已完成 3=已取消 */
    private Integer status;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
