package com.vago.user.handler;

import com.vago.user.common.Result;
import com.vago.user.common.ResultCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理器
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * 处理 @Valid 校验失败（参数格式错误）
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationException(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> e.getField() + ": " + e.getDefaultMessage())
                .findFirst()
                .orElse("请求参数格式不合法");
        log.warn("参数校验失败: {}", message);
        return Result.fail(ResultCode.PARAM_INVALID.getCode(), message);
    }

    /**
     * 兜底处理所有未捕获的运行时异常
     */
    @ExceptionHandler(RuntimeException.class)
    public Result<Void> handleRuntimeException(RuntimeException ex) {
        log.error("服务器内部错误", ex);
        return Result.fail(ResultCode.INTERNAL_ERROR);
    }

    /**
     * 兜底处理所有 Exception
     */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception ex) {
        log.error("未知异常", ex);
        return Result.fail(ResultCode.INTERNAL_ERROR);
    }

}
