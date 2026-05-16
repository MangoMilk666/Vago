package com.vago.user.controller;

import com.vago.user.common.Result;
import com.vago.user.context.BaseContext;
import com.vago.user.model.dto.*;
import com.vago.user.model.vo.*;
import com.vago.user.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/user")
@Slf4j
@Tag(name = "C端用户相关接口")
public class UserController {

    @Autowired
    private UserService userService;

    // ─────────────────────────────────────────────
    // 短信验证码
    // ─────────────────────────────────────────────

    @PostMapping("/sms/send")
    @Operation(summary = "发送短信验证码")
    public Result<Map<String, Integer>> sendSmsCode(@Valid @RequestBody SmsSendDTO dto) {
        log.info("发送短信验证码: {}", dto.getPhone());
        userService.sendSmsCode(dto);
        return Result.success("验证码已发送", Map.of("expireSeconds", 300));
    }

    // ─────────────────────────────────────────────
    // 注册与登录
    // ─────────────────────────────────────────────

    @PostMapping("/register")
    @Operation(summary = "手机号注册")
    public Result<LoginVO> register(@Valid @RequestBody UserRegisterDTO dto) {
        log.info("用户注册: {}", dto.getPhone());
        return Result.success("注册成功", userService.register(dto));
    }

    @PostMapping("/login/phone")
    @Operation(summary = "手机号 + 短信验证码登录")
    public Result<LoginVO> loginByPhone(@Valid @RequestBody UserLoginPhoneDTO dto) {
        log.info("手机号登录: {}", dto.getPhone());
        return Result.success("登录成功", userService.loginByPhone(dto));
    }

    @PostMapping("/login/oauth")
    @Operation(summary = "第三方 OAuth 登录（微信/Apple）")
    public Result<LoginVO> loginByOAuth(@Valid @RequestBody UserLoginOAuthDTO dto) {
        log.info("OAuth 登录: provider={}", dto.getProvider());
        return Result.success("登录成功", userService.loginByOAuth(dto));
    }

    // ─────────────────────────────────────────────
    // Token 管理
    // ─────────────────────────────────────────────

    @PostMapping("/token/refresh")
    @Operation(summary = "刷新 Access Token")
    public Result<TokenVO> refreshToken(@Valid @RequestBody TokenRefreshDTO dto) {
        return Result.success(userService.refreshToken(dto));
    }

    @PostMapping("/logout")
    @Operation(summary = "退出登录", security = @SecurityRequirement(name = "Bearer Token"))
    public Result<Void> logout(@RequestHeader(value = "authorization", required = false) String authHeader) {
        log.info("用户退出登录: {}", BaseContext.getCurrentUuid());
        String token = resolveToken(authHeader);
        userService.logout(token);
        return Result.success("已退出登录", null);
    }

    // ─────────────────────────────────────────────
    // 用户信息
    // ─────────────────────────────────────────────

    @GetMapping("/profile")
    @Operation(summary = "获取当前用户信息", security = @SecurityRequirement(name = "Bearer Token"))
    public Result<UserVO> getProfile() {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("获取用户信息: {}", userUuid);
        return Result.success(userService.getProfile(userUuid));
    }

    @PutMapping("/profile")
    @Operation(summary = "修改用户信息", security = @SecurityRequirement(name = "Bearer Token"))
    public Result<UserVO> updateProfile(@Valid @RequestBody UserUpdateProfileDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("修改用户信息: {}", userUuid);
        return Result.success("修改成功", userService.updateProfile(userUuid, dto));
    }

    // ─────────────────────────────────────────────
    // 用户设置
    // ─────────────────────────────────────────────

    @GetMapping("/settings")
    @Operation(summary = "获取用户偏好设置", security = @SecurityRequirement(name = "Bearer Token"))
    public Result<UserSettingsVO> getSettings() {
        String userUuid = BaseContext.getCurrentUuid();
        return Result.success(userService.getSettings(userUuid));
    }

    @PutMapping("/settings")
    @Operation(summary = "更新用户偏好设置", security = @SecurityRequirement(name = "Bearer Token"))
    public Result<UserSettingsVO> updateSettings(@Valid @RequestBody UserUpdateSettingsDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("更新用户设置: {}", userUuid);
        return Result.success("设置已更新", userService.updateSettings(userUuid, dto));
    }

    // ─────────────────────────────────────────────
    // 账户管理
    // ─────────────────────────────────────────────

    @DeleteMapping("/account")
    @Operation(summary = "申请注销账号", security = @SecurityRequirement(name = "Bearer Token"))
    public Result<Map<String, String>> cancelAccount(@Valid @RequestBody AccountCancelDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("用户申请注销: {}", userUuid);
        String deadline = userService.cancelAccount(userUuid, dto);
        return Result.success("注销申请已提交，7日内可撤销", Map.of("cancelDeadline", deadline));
    }

    @PostMapping("/account/cancel-revoke")
    @Operation(summary = "撤销注销申请", security = @SecurityRequirement(name = "Bearer Token"))
    public Result<Void> revokeCancelAccount() {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("用户撤销注销申请: {}", userUuid);
        userService.revokeCancelAccount(userUuid);
        return Result.success("注销申请已撤销，账号恢复正常", null);
    }

    // ─────────────────────────────────────────────
    // 私有工具方法
    // ─────────────────────────────────────────────

    private String resolveToken(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7);
        }
        return null;
    }
}
