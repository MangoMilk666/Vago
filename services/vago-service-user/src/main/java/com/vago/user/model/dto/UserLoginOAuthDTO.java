package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

@Data
@Schema(description = "第三方 OAuth 登录请求")
public class UserLoginOAuthDTO {

    @NotBlank(message = "provider 不能为空")
    @Pattern(regexp = "^(wechat|apple)$", message = "provider 仅支持 wechat / apple")
    @Schema(description = "OAuth 提供方", allowableValues = {"wechat", "apple"})
    private String provider;

    @NotBlank(message = "authCode 不能为空")
    @Schema(description = "客户端从第三方获取的授权码")
    private String authCode;

    @Schema(description = "设备唯一标识")
    private String deviceId;
}
