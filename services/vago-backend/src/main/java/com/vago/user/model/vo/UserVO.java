package com.vago.user.model.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

@Data
@Builder
@Schema(description = "用户信息视图")
public class UserVO {

    @Schema(description = "用户业务 ID（UUID）")
    private String uuid;

    @Schema(description = "昵称")
    private String nickname;

    @Schema(description = "手机号（中间 4 位脱敏）")
    private String phone;

    @Schema(description = "邮箱")
    private String email;

    @Schema(description = "头像访问 URL（CDN 地址）")
    private String avatarUrl;

    @Schema(description = "订阅套餐：0=免费版 1=付费版")
    private Integer planType;

    @Schema(description = "攻略库配额上限")
    private Integer articleQuota;

    @Schema(description = "账户状态：1=正常 2=封禁 3=注销中")
    private Integer status;

    @Schema(description = "注册时间（UTC）")
    private LocalDateTime createdAt;

    @Schema(description = "已绑定的第三方登录平台列表")
    private List<String> oauthProviders;
}
