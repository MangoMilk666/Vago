package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
@Schema(description = "申请注销账号请求")
public class AccountCancelDTO {

    @NotBlank(message = "验证码不能为空")
    @Pattern(regexp = "^\\d{6}$", message = "验证码为 6 位数字")
    @Schema(description = "短信验证码")
    private String smsCode;

    @Size(max = 200, message = "注销原因最多 200 字")
    @Schema(description = "注销原因（可选）")
    private String reason;
}
