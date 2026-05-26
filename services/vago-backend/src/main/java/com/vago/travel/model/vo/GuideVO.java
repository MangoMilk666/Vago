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

    /** 0=草稿 1=已发布 */
    private Integer status;

    // 作者信息（公开列表时展示）
    private String authorUuid;
    private String authorNickname;
    private String authorAvatarKey;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
