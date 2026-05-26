package com.vago.common;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 通用分页返回体
 *
 * @param <T> 数据行类型
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PageVO<T> {

    /** 总记录数 */
    private long total;

    /** 当前页（从 1 开始） */
    private int page;

    /** 每页大小 */
    private int size;

    /** 当前页数据 */
    private List<T> records;
}
