package com.vago.travel.service;

import com.vago.travel.model.dto.PlanCreateDTO;
import com.vago.travel.model.dto.PlanUpdateDTO;
import com.vago.travel.model.vo.PlanVO;
import com.vago.travel.model.vo.TripVO;

import java.util.List;

public interface PlanService {

    /** 创建计划草稿 */
    PlanVO create(String userUuid, PlanCreateDTO dto);

    /** 查询当前用户全部计划 */
    List<PlanVO> listMyPlans(String userUuid);

    /** 查询计划详情 */
    PlanVO getDetail(String userUuid, String planUuid);

    /** 更新计划 */
    PlanVO update(String userUuid, String planUuid, PlanUpdateDTO dto);

    /** 删除计划（软删除） */
    void delete(String userUuid, String planUuid);

    /**
     * 将草稿计划转为正式行程
     *
     * @return 新创建的行程 VO
     */
    TripVO convertToTrip(String userUuid, String planUuid);
}
