package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
@Schema(description = "第三方 OAuth 登录请求")
public class UserLoginOAuthDTO {

    @NotBlank(message = "provider 不能为空")
    @Schema(description = "OAuth 提供方", example = "github")
    private String provider;

    @NotBlank(message = "authCode 不能为空")
    @Schema(description = "客户端从第三方获取的授权码")
    private String authCode;

    @NotBlank(message = "redirectUri 不能为空")
    @Schema(description = "本次授权使用的回调地址，需与 provider 配置保持一致")
    private String redirectUri;

    @Schema(description = "设备唯一标识")
    private String deviceId;
}
