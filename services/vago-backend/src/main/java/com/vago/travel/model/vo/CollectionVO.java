package com.vago.travel.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CollectionVO {
    private String uuid;            // 收藏夹 UUID
    private String userUuid;        // 所属用户
    private String name;            // 收藏夹名称
    private Integer type;           // 0=RAG(AI知识库), 1=NORMAL(普通收藏)
    private String description;     // 收藏夹描述
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
