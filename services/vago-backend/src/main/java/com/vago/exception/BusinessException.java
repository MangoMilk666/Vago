package com.vago.exception;

import com.vago.common.ResultCode;
import lombok.Getter;

/**
 * 业务异常：由 Service 层主动抛出，携带业务错误码。
 * GlobalExceptionHandler 会将其转换为 Result.fail(...) 响应，不打印堆栈。
 */
@Getter
public class BusinessException extends RuntimeException {

    private final Integer code;

    public BusinessException(ResultCode resultCode) {
        super(resultCode.getMessage());
        this.code = resultCode.getCode();
    }

    public BusinessException(Integer code, String message) {
        super(message);
        this.code = code;
    }
}
