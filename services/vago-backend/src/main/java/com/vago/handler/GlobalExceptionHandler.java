package com.vago.handler;

import com.vago.common.Result;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理器
 * 优先级：BusinessException > MethodArgumentNotValidException > RuntimeException > Exception
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * 业务异常（由 Service 层主动抛出，已知错误，只 warn 不打堆栈）
     */
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException ex) {
        log.warn("业务异常: code={}, message={}", ex.getCode(), ex.getMessage());
        return Result.fail(ex.getCode(), ex.getMessage());
    }

    /**
     * 参数校验失败（@Valid）
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
     * 未预期的运行时异常（打堆栈，便于排查）
     * 异常信息透传到响应体，方便开发阶段定位问题
     */
    @ExceptionHandler(RuntimeException.class)
    public Result<Void> handleRuntimeException(RuntimeException ex) {
        log.error("服务器内部错误: {}", ex.getMessage(), ex);
        String detail = ex.getClass().getSimpleName() + ": " + ex.getMessage();
        return Result.fail(ResultCode.INTERNAL_ERROR.getCode(), detail);
    }

    /**
     * 兜底：所有其他异常
     */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception ex) {
        log.error("未知异常: {}", ex.getMessage(), ex);
        String detail = ex.getClass().getSimpleName() + ": " + ex.getMessage();
        return Result.fail(ResultCode.INTERNAL_ERROR.getCode(), detail);
    }
}
