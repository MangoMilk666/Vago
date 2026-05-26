package com.vago.travel.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

@Data
public class GuideCreateDTO {

    @NotBlank(message = "攻略标题不能为空")
    @Size(max = 100, message = "标题最长 100 个字符")
    private String title;

    @Size(max = 200, message = "地点描述最长 200 个字符")
    private String destination;

    /** 封面图 OSS Key */
    private String coverImageKey;

    /** 图片列表（OSS Key 或 URL） */
    private List<String> imageKeys;

    @NotBlank(message = "攻略正文不能为空")
    private String content;

    /** 标签列表 */
    private List<String> tags;

    /**
     * 发布状态：0=草稿（仅自己可见），1=发布（公开）
     * 不传时默认 1（直接发布）
     */
    private Integer status;
}
