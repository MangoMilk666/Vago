package com.vago.travel.controller;

import com.vago.common.Result;
import com.vago.common.ResultCode;
import com.vago.context.BaseContext;
import com.vago.exception.BusinessException;
import com.vago.travel.mapper.TripMapper;
import com.vago.travel.model.dto.ItineraryDayUpdateDTO;
import com.vago.travel.model.entity.ItineraryDay;
import com.vago.travel.model.entity.Trip;
import com.vago.travel.model.vo.ItineraryDayVO;
import com.vago.travel.service.ItineraryService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 行程每日规划接口
 * Base: /api/v1/travel/trips/{tripUuid}/days
 */
@Tag(name = "行程每日规划")
@RestController
@RequestMapping("/api/v1/travel/trips/{tripUuid}/days")
public class TripItineraryController {

    @Autowired private ItineraryService itineraryService;
    @Autowired private TripMapper       tripMapper;

    @Operation(summary = "获取行程的全部每日规划（懒初始化）")
    @GetMapping
    public Result<List<ItineraryDayVO>> getDays(@PathVariable("tripUuid") String tripUuid) {
        checkOwner(tripUuid);
        return Result.success(
                itineraryService.getDays(tripUuid, ItineraryDay.REF_TYPE_TRIP));
    }

    @Operation(summary = "更新第 N 天的行程（含景点全量替换）")
    @PutMapping("/{dayIndex}")
    public Result<ItineraryDayVO> updateDay(@PathVariable("tripUuid") String tripUuid,
                                             @PathVariable("dayIndex") int dayIndex,
                                             @Valid @RequestBody ItineraryDayUpdateDTO dto) {
        checkOwner(tripUuid);
        return Result.success(
                itineraryService.updateDay(tripUuid, ItineraryDay.REF_TYPE_TRIP, dayIndex, dto));
    }

    // ── 校验行程归属当前用户 ───────────────────────────────────────────────────
    private void checkOwner(String tripUuid) {
        Trip trip = tripMapper.getByUuid(tripUuid);
        if (trip == null) throw new BusinessException(ResultCode.TRIP_NOT_FOUND);
        if (!BaseContext.getCurrentUuid().equals(trip.getUserUuid())) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }
    }
}
