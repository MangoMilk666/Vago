package com.vago.travel.model.dto;

import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

@Data
public class GuideUpdateDTO {

    @Size(max = 100, message = "标题最长 100 个字符")
    private String title;

    @Size(max = 200, message = "地点描述最长 200 个字符")
    private String destination;

    private String coverImageKey;

    private List<String> imageKeys;

    private String content;

    private List<String> tags;

    /** 0=草稿 1=已发布 */
    private Integer status;
}
