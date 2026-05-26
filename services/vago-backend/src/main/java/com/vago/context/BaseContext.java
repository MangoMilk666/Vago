package com.vago.context;

/**
 * 上下文工具类
 * 通过 ThreadLocal 在同一个线程内传递当前用户的 UUID
 */
public class BaseContext {

    private static final ThreadLocal<String> threadLocal = new ThreadLocal<>();

    public static void setCurrentUuid(String uuid) {
        threadLocal.set(uuid);
    }

    public static String getCurrentUuid() {
        return threadLocal.get();
    }

    public static void removeCurrentUuid() {
        threadLocal.remove();
    }
}
