package com.vago.travel.controller;

import com.vago.common.Result;
import com.vago.context.BaseContext;
import com.vago.travel.model.dto.TripCreateDTO;
import com.vago.travel.model.dto.TripUpdateDTO;
import com.vago.travel.model.vo.TripVO;
import com.vago.travel.service.TripService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 行程管理接口
 * Base: /api/v1/travel/trips
 */
@Tag(name = "行程管理")
@RestController
@RequestMapping("/api/v1/travel/trips")
public class TripController {

    @Autowired
    private TripService tripService;

    @Operation(summary = "创建行程")
    @PostMapping
    public Result<TripVO> create(@Valid @RequestBody TripCreateDTO dto) {
        return Result.success(tripService.create(BaseContext.getCurrentUuid(), dto));
    }

    @Operation(summary = "查询我的全部行程")
    @GetMapping
    public Result<List<TripVO>> listMy() {
        return Result.success(tripService.listMyTrips(BaseContext.getCurrentUuid()));
    }

    @Operation(summary = "查询历史（已完成）行程")
    @GetMapping("/history")
    public Result<List<TripVO>> listHistory() {
        return Result.success(tripService.listHistory(BaseContext.getCurrentUuid()));
    }

    @Operation(summary = "查询行程详情")
    @GetMapping("/{uuid}")
    public Result<TripVO> getDetail(@PathVariable String uuid) {
        return Result.success(tripService.getDetail(BaseContext.getCurrentUuid(), uuid));
    }

    @Operation(summary = "更新行程")
    @PutMapping("/{uuid}")
    public Result<TripVO> update(@PathVariable String uuid,
                                 @Valid @RequestBody TripUpdateDTO dto) {
        return Result.success(tripService.update(BaseContext.getCurrentUuid(), uuid, dto));
    }

    @Operation(summary = "删除行程")
    @DeleteMapping("/{uuid}")
    public Result delete(@PathVariable String uuid) {
        tripService.delete(BaseContext.getCurrentUuid(), uuid);
        return Result.success();
    }
}
