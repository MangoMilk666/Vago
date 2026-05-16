package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

@Data
@Schema(description = "发送短信验证码请求")
public class SmsSendDTO {

    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^\\+[1-9]\\d{6,14}$", message = "手机号须为 E.164 格式，如 +8613800138000")
    @Schema(description = "E.164 格式手机号", example = "+8613800138000")
    private String phone;

    @NotBlank(message = "场景不能为空")
    @Pattern(regexp = "^(REGISTER|LOGIN|CANCEL_ACCOUNT)$", message = "scene 枚举值非法")
    @Schema(description = "发送场景", allowableValues = {"REGISTER", "LOGIN", "CANCEL_ACCOUNT"})
    private String scene;
}
