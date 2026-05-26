package com.vago.user.model.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
@Schema(description = "Token 刷新响应")
public class TokenVO {

    @Schema(description = "新的访问令牌")
    private String accessToken;

    @Schema(description = "新的刷新令牌（旧令牌立即失效）")
    private String refreshToken;

    @Schema(description = "accessToken 有效期（秒）")
    private Long expiresIn;
}
