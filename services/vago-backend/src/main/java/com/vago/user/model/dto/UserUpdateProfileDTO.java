package com.vago.user.model.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
@Schema(description = "修改用户信息请求（仅传需修改字段）")
public class UserUpdateProfileDTO {

    @Size(min = 2, max = 20, message = "昵称长度为 2-20 个字符")
    @Schema(description = "新昵称")
    private String nickname;

    @Email(message = "邮箱格式不合法")
    @Schema(description = "邮箱")
    private String email;

    @Schema(description = "已上传头像的图片 UUID")
    private String avatarUuid;
}
