package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
@Schema(description = "手机号注册请求")
public class UserRegisterDTO {

    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^\\+[1-9]\\d{6,14}$", message = "手机号须为 E.164 格式")
    @Schema(description = "E.164 格式手机号", example = "+8613800138000")
    private String phone;

    @NotBlank(message = "验证码不能为空")
    @Pattern(regexp = "^\\d{6}$", message = "验证码为 6 位数字")
    @Schema(description = "6 位短信验证码")
    private String smsCode;

    @NotBlank(message = "昵称不能为空")
    @Size(min = 2, max = 20, message = "昵称长度为 2-20 个字符")
    @Schema(description = "用户昵称", example = "旅行者小明")
    private String nickname;

    @Schema(description = "设备唯一标识（用于风控）")
    private String deviceId;
}
