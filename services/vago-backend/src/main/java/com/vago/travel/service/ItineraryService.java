package com.vago.travel.service;

import com.vago.travel.model.dto.ItineraryDayUpdateDTO;
import com.vago.travel.model.vo.ItineraryDayVO;

import java.util.List;

public interface ItineraryService {

    /**
     * 获取某行程/计划的全部每日行程（懒初始化）
     *
     * <p>调用时会自动对比日期区间与已有 day 记录：
     * <ul>
     *   <li>日期区间内缺失的 day → 自动创建空记录</li>
     *   <li>已有 day 的数据原样返回</li>
     * </ul>
     *
     * @param refUuid 行程或计划的 UUID
     * @param refType {@code ItineraryDay.REF_TYPE_TRIP} or {@code REF_TYPE_PLAN}
     */
    List<ItineraryDayVO> getDays(String refUuid, int refType);

    /**
     * 更新某一天的行程数据（含景点全量替换）
     *
     * @param refUuid  行程或计划 UUID（用于权限校验）
     * @param refType  归属类型
     * @param dayIndex 第几天（1 起始）
     * @param dto      更新内容
     */
    ItineraryDayVO updateDay(String refUuid, int refType, int dayIndex,
                             ItineraryDayUpdateDTO dto);

    /**
     * 将某计划的所有每日行程复制到新行程（plan → trip 转换时调用）
     *
     * @param planUuid 原计划 UUID
     * @param tripUuid 目标行程 UUID
     */
    void copyDaysFromPlanToTrip(String planUuid, String tripUuid);
}
