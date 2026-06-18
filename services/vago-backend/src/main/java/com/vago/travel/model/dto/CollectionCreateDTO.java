package com.vago.travel.model.dto;

import lombok.Data;

/**
 * 创建收藏夹请求体。
 * type 默认为 NORMAL(1)，用户创建 RAG 收藏夹时需显式传入 0。
 */
@Data
public class CollectionCreateDTO {
    private String name;          // 收藏夹名称
    private String description;   // 收藏夹描述
    private Integer type = 1;     // 0=RAG(AI知识库), 1=NORMAL(普通), 默认为普通
}
