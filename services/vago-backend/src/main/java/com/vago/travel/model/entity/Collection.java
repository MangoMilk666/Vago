package com.vago.travel.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 收藏夹信息实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Collection implements Serializable {
    private String uuid;   // 收藏夹 UUID
    private String userUuid;   // 所属用户
    private String name;        // 收藏夹名称
    private Integer type;        // 0=RAG(AI知识库), 1=NORMAL(普通收藏)
    private String description;   // 收藏夹描述
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
