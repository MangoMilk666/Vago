package com.vago.travel.model.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class CollectionCreateDTO {
    private String name;        // 收藏夹名称
    private String description;   // 收藏夹备注
}
