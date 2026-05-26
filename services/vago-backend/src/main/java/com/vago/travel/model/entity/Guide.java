package com.vago.travel.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 旅游攻略实体
 *
 * <p>imageKeys / tags 在数据库中存储为 JSON 字符串（如 ["key1","key2"]），
 * 由 Service 层负责与 List<String> 之间的序列化/反序列化。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Guide implements Serializable {

    /** DB 自增主键 */
    private Long id;

    /** 对外业务 ID */
    private String uuid;

    /** 归属用户 UUID */
    private String userUuid;

    /** 攻略标题 */
    private String title;

    /** 目的地 */
    private String destination;

    /** 封面图 OSS Key */
    private String coverImageKey;

    /** 图片列表（JSON 字符串，存多张图片的 OSS Key 或 URL） */
    private String imageKeys;

    /** 攻略正文 */
    private String content;

    /** 标签列表（JSON 字符串，如 ["美食","打卡"]） */
    private String tags;

    /** 浏览量 */
    private Integer viewCount;

    /** 点赞数 */
    private Integer likeCount;

    /**
     * 状态
     * <ul>
     *   <li>0 = 草稿（仅自己可见）</li>
     *   <li>1 = 已发布（公开）</li>
     * </ul>
     */
    private Integer status;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    /** 软删除时间 */
    private LocalDateTime deletedAt;
}
