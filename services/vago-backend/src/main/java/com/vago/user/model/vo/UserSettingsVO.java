package com.vago.user.model.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
@Schema(description = "用户偏好设置视图")
public class UserSettingsVO {

    @Schema(description = "GPS 采集模式：0=省电 1=标准 2=精细")
    private Integer gpsMode;

    @Schema(description = "迷雾解锁半径（米）")
    private Integer fogUnlockRadiusM;

    @Schema(description = "默认可见性：0=私密 1=链接可见 2=公开")
    private Integer defaultVisibility;

    @Schema(description = "语言")
    private String language;

    @Schema(description = "时区")
    private String timezone;

    @Schema(description = "行程结束提醒开关")
    private Boolean notificationCheckin;
}
