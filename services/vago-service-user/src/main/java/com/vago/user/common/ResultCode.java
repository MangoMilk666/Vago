package com.vago.user.common;

import lombok.Getter;

@Getter
public enum ResultCode {

    SUCCESS(200, "success"),

    // 4xx 业务错误
    PARAM_INVALID(4001, "请求参数格式不合法"),
    SMS_CODE_INVALID(4002, "验证码错误或已过期"),
    OAUTH_CODE_INVALID(4003, "OAuth authCode 无效"),
    TOKEN_INVALID(4011, "Token 无效，请重新登录"),
    TOKEN_EXPIRED(4012, "Token 已过期，请刷新"),
    ACCOUNT_BANNED(4031, "账号已被封禁"),
    ACCOUNT_CANCELLING(4032, "账号注销中，无法登录"),
    RESOURCE_NOT_FOUND(4041, "资源不存在"),
    PHONE_ALREADY_REGISTERED(4090, "手机号已注册，请直接登录"),
    EMAIL_ALREADY_USED(4091, "邮箱已被其他账号使用"),
    ACCOUNT_ALREADY_CANCELLING(4093, "账号已在注销中"),
    ACCOUNT_NOT_CANCELLING(4094, "账号不在注销状态"),
    CANCEL_REVOKE_EXPIRED(4095, "注销撤销期已过"),
    SMS_RATE_LIMIT(4291, "发送频率超限，请稍后再试"),

    // 5xx 服务端错误
    SMS_SERVICE_ERROR(5001, "短信服务暂不可用"),
    OAUTH_SERVICE_ERROR(5002, "第三方登录服务异常"),
    INTERNAL_ERROR(5000, "服务器内部错误");

    private final Integer code;
    private final String message;

    ResultCode(Integer code, String message) {
        this.code = code;
        this.message = message;
    }
}
