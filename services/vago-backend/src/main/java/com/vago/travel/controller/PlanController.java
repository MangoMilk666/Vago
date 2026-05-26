package com.vago.travel.controller;

import com.vago.common.Result;
import com.vago.context.BaseContext;
import com.vago.travel.model.dto.PlanCreateDTO;
import com.vago.travel.model.dto.PlanUpdateDTO;
import com.vago.travel.model.vo.PlanVO;
import com.vago.travel.model.vo.TripVO;
import com.vago.travel.service.PlanService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 旅行计划接口
 * Base: /api/v1/travel/plans
 */
@Tag(name = "旅行计划")
@RestController
@RequestMapping("/api/v1/travel/plans")
public class PlanController {

    @Autowired
    private PlanService planService;

    @Operation(summary = "创建计划草稿")
    @PostMapping
    public Result<PlanVO> create(@Valid @RequestBody PlanCreateDTO dto) {
        return Result.success(planService.create(BaseContext.getCurrentUuid(), dto));
    }

    @Operation(summary = "查询我的全部计划")
    @GetMapping
    public Result<List<PlanVO>> listMy() {
        return Result.success(planService.listMyPlans(BaseContext.getCurrentUuid()));
    }

    @Operation(summary = "查询计划详情")
    @GetMapping("/{uuid}")
    public Result<PlanVO> getDetail(@PathVariable String uuid) {
        return Result.success(planService.getDetail(BaseContext.getCurrentUuid(), uuid));
    }

    @Operation(summary = "更新计划")
    @PutMapping("/{uuid}")
    public Result<PlanVO> update(@PathVariable String uuid,
                                 @Valid @RequestBody PlanUpdateDTO dto) {
        return Result.success(planService.update(BaseContext.getCurrentUuid(), uuid, dto));
    }

    @Operation(summary = "删除计划")
    @DeleteMapping("/{uuid}")
    public Result delete(@PathVariable String uuid) {
        planService.delete(BaseContext.getCurrentUuid(), uuid);
        return Result.success();
    }

    @Operation(summary = "将计划转为正式行程")
    @PostMapping("/{uuid}/convert")
    public Result<TripVO> convertToTrip(@PathVariable String uuid) {
        return Result.success(planService.convertToTrip(BaseContext.getCurrentUuid(), uuid));
    }
}
