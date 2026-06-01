package com.vago.travel.model.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GuideVO {

    private String uuid;
    private String title;
    private String destination;
    private String coverImageKey;

    /** 图片列表（已反序列化） */
    private List<String> imageKeys;

    private String content;

    /** 标签列表（已反序列化） */
    private List<String> tags;

    private Integer viewCount;
    private Integer likeCount;

    /** 当前请求用户是否已点赞（仅 getDetail 填充，列表接口为 null） */
    private Boolean liked;

    /** 0=草稿 1=已发布 */
    private Integer status;

    /**
     * RAG 向量化状态（草稿时为 null）
     * <ul>
     *   <li>0 = PENDING   — 已发布，等待向量化</li>
     *   <li>1 = INDEXING  — 正在向量化</li>
     *   <li>2 = INDEXED   — 已完成，可被 AI 检索</li>
     *   <li>3 = FAILED    — 向量化失败</li>
     * </ul>
     */
    private Integer aiStatus;

    // 作者信息（公开列表时展示）
    private String authorUuid;
    private String authorNickname;
    private String authorAvatarKey;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
