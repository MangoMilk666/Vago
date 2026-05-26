package com.vago.travel.controller;

import com.vago.common.PageVO;
import com.vago.common.Result;
import com.vago.context.BaseContext;
import com.vago.travel.model.dto.GuideCreateDTO;
import com.vago.travel.model.dto.GuideUpdateDTO;
import com.vago.travel.model.vo.GuideVO;
import com.vago.travel.service.GuideService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 旅游攻略相关接口
 * Base: /api/v1/travel/guides
 */
@Tag(name = "旅游攻略")
@RestController
@RequestMapping("/api/v1/travel/guides")
public class GuideController {

    @Autowired
    private GuideService guideService;

    /**
     * 公开攻略列表（分页）——无需登录
     * 独立路径 /discover 避免与 POST /guides（需鉴权）产生 excludePathPatterns 冲突
     */
    @Operation(summary = "公开攻略列表（分页，无需登录）")
    @GetMapping("/discover")
    public Result<PageVO<GuideVO>> listPublished(
            @RequestParam(value = "page", defaultValue = "1") int page,
            @RequestParam(value = "size", defaultValue = "20") int size) {
        return Result.success(guideService.listPublished(page, size));
    }

    @Operation(summary = "我的攻略列表（含草稿）")
    @GetMapping("/mine")
    public Result<List<GuideVO>> listMine() {
        return Result.success(guideService.listMine(BaseContext.getCurrentUuid()));
    }

    @Operation(summary = "查看攻略详情")
    @GetMapping("/{uuid}")
    public Result<GuideVO> getDetail(@PathVariable("uuid") String uuid) {
        return Result.success(guideService.getDetail(BaseContext.getCurrentUuid(), uuid));
    }

    @Operation(summary = "创建攻略")
    @PostMapping
    public Result<GuideVO> create(@Valid @RequestBody GuideCreateDTO dto) {
        return Result.success(guideService.create(BaseContext.getCurrentUuid(), dto));
    }

    @Operation(summary = "更新攻略")
    @PutMapping("/{uuid}")
    public Result<GuideVO> update(@PathVariable("uuid") String uuid,
                                  @Valid @RequestBody GuideUpdateDTO dto) {
        return Result.success(guideService.update(BaseContext.getCurrentUuid(), uuid, dto));
    }

    @Operation(summary = "删除攻略")
    @DeleteMapping("/{uuid}")
    public Result<String> delete(@PathVariable("uuid") String uuid) {
        guideService.delete(BaseContext.getCurrentUuid(), uuid);
        return Result.success();
    }

    @Operation(summary = "点赞攻略")
    @PostMapping("/{uuid}/like")
    public Result like(@PathVariable("uuid") String uuid) {
        guideService.like(uuid);
        return Result.success();
    }
}
