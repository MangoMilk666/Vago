package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

@Data
@Schema(description = "更新用户偏好设置请求（仅传需修改字段）")
public class UserUpdateSettingsDTO {

    @Min(value = 0, message = "gpsMode 枚举值为 0/1/2")
    @Max(value = 2, message = "gpsMode 枚举值为 0/1/2")
    @Schema(description = "GPS 采集模式：0=省电 1=标准 2=精细")
    private Integer gpsMode;

    @Min(value = 100, message = "解锁半径最小 100 米")
    @Max(value = 1000, message = "解锁半径最大 1000 米")
    @Schema(description = "迷雾解锁半径（米）")
    private Integer fogUnlockRadiusM;

    @Min(value = 0, message = "defaultVisibility 枚举值为 0/1/2")
    @Max(value = 2, message = "defaultVisibility 枚举值为 0/1/2")
    @Schema(description = "默认可见性：0=私密 1=链接可见 2=公开")
    private Integer defaultVisibility;

    @Schema(description = "语言，如 zh-CN / en-US")
    private String language;

    @Schema(description = "时区，如 Asia/Shanghai")
    private String timezone;

    @Schema(description = "行程结束提醒：true=开启 false=关闭")
    private Boolean notificationCheckin;
}
