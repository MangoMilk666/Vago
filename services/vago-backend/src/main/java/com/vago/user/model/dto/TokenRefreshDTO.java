package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
@Schema(description = "刷新 Token 请求")
public class TokenRefreshDTO {

    @NotBlank(message = "refreshToken 不能为空")
    @Schema(description = "登录时下发的 refreshToken")
    private String refreshToken;
}
