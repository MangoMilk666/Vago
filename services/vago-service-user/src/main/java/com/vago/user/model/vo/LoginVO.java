package com.vago.user.model.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
@Schema(description = "登录/注册成功响应")
public class LoginVO {

    @Schema(description = "访问令牌")
    private String accessToken;

    @Schema(description = "刷新令牌（有效期 30 天）")
    private String refreshToken;

    @Schema(description = "accessToken 有效期（秒）")
    private Long expiresIn;

    @Schema(description = "是否为新注册用户（OAuth 登录时有意义）")
    private Boolean isNewUser;

    @Schema(description = "用户信息")
    private UserVO userInfo;
}
