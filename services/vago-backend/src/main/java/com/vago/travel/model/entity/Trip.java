package com.vago.travel.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 行程实体（正式行程，已出行或计划出行）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Trip implements Serializable {

    /** DB 自增主键 */
    private Long id;

    /** 对外业务 ID */
    private String uuid;

    /** 归属用户 UUID */
    private String userUuid;

    /** 行程标题 */
    private String title;

    /** 行程地点（单主目的地描述） */
    private String destination;

    /** 封面图 OSS Key（可空） */
    private String coverImageKey;

    /** 出发日期 */
    private LocalDate startDate;

    /** 返回日期 */
    private LocalDate endDate;

    /**
     * 行程状态
     * <ul>
     *   <li>1 = 计划中</li>
     *   <li>2 = 已完成</li>
     *   <li>3 = 已取消</li>
     * </ul>
     */
    private Integer status;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    /** 软删除时间，NULL 表示未删除 */
    private LocalDateTime deletedAt;
}
