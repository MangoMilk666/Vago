package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

@Data
@Schema(description = "发送短信验证码请求")
public class SmsSendDTO {

    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "请输入有效的 11 位手机号")
    @Schema(description = "手机号（国内 11 位）", example = "13800138000")
    private String phone;

    @Schema(description = "发送场景（可选）", allowableValues = {"REGISTER", "LOGIN", "CANCEL_ACCOUNT"})
    private String scene;
}
