package com.vago.user.model.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 用户偏好设置实体类（与 users 一对一）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserSettings implements Serializable {

    /** 与 users.id 一对一，兼作主键 */
    private Long userId;

    /** GPS 采集模式：0=省电 1=标准 2=精细 */
    private Integer gpsMode;

    /** 迷雾解锁半径（米） */
    private Integer fogUnlockRadiusM;

    /** 存档默认可见性：0=私密 1=链接可见 2=公开 */
    private Integer defaultVisibility;

    private String language;

    private String timezone;

    /** 行程结束提醒开关：1=开 0=关 */
    private Integer notificationCheckin;

    private LocalDateTime updatedAt;
}
