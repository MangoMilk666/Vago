package com.vago.travel.controller;

import com.vago.common.Result;
import com.vago.common.ResultCode;
import com.vago.context.BaseContext;
import com.vago.exception.BusinessException;
import com.vago.travel.mapper.PlanMapper;
import com.vago.travel.model.dto.ItineraryDayUpdateDTO;
import com.vago.travel.model.entity.ItineraryDay;
import com.vago.travel.model.entity.Plan;
import com.vago.travel.model.vo.ItineraryDayVO;
import com.vago.travel.service.ItineraryService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 计划每日规划接口
 * Base: /api/v1/travel/plans/{planUuid}/days
 */
@Tag(name = "计划每日规划")
@RestController
@RequestMapping("/api/v1/travel/plans/{planUuid}/days")
public class PlanItineraryController {

    @Autowired private ItineraryService itineraryService;
    @Autowired private PlanMapper       planMapper;

    @Operation(summary = "获取计划的全部每日规划（懒初始化）")
    @GetMapping
    public Result<List<ItineraryDayVO>> getDays(@PathVariable("planUuid") String planUuid) {
        checkOwner(planUuid);
        return Result.success(
                itineraryService.getDays(planUuid, ItineraryDay.REF_TYPE_PLAN));
    }

    @Operation(summary = "更新第 N 天的计划（含景点全量替换）")
    @PutMapping("/{dayIndex}")
    public Result<ItineraryDayVO> updateDay(@PathVariable("planUuid") String planUuid,
                                             @PathVariable("dayIndex") int dayIndex,
                                             @Valid @RequestBody ItineraryDayUpdateDTO dto) {
        checkOwner(planUuid);
        return Result.success(
                itineraryService.updateDay(planUuid, ItineraryDay.REF_TYPE_PLAN, dayIndex, dto));
    }

    // ── 校验计划归属当前用户 ───────────────────────────────────────────────────
    private void checkOwner(String planUuid) {
        Plan plan = planMapper.getByUuid(planUuid);
        if (plan == null) throw new BusinessException(ResultCode.PLAN_NOT_FOUND);
        if (!BaseContext.getCurrentUuid().equals(plan.getUserUuid())) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }
    }
}
