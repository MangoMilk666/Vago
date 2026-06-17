package com.vago.travel.controller;

import com.vago.common.Result;
import com.vago.context.BaseContext;
import com.vago.travel.model.dto.CollectionCreateDTO;
import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.dto.GuideSavedDTO;
import com.vago.travel.model.entity.Collection;
import com.vago.travel.model.vo.CollectionVO;
import com.vago.travel.model.vo.GuideVO;
import com.vago.travel.service.CollectionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 帖子收藏夹相关接口
 * Base: /api/v1/travel/collections
 */
@Tag(name = "攻略收藏夹")
@RequestMapping("/api/v1/travel/collections")
@RestController
@Slf4j
public class CollectionController {

    @Autowired
    private CollectionService collectionService;

    @Operation(summary = "创建收藏夹")
    @PostMapping()
    public Result<CollectionVO> create(@Valid @RequestBody CollectionCreateDTO dto){
        log.info("创建收藏夹: {}", dto);
        return Result.success(collectionService.create(BaseContext.getCurrentUuid(), dto));
    }

    @Operation(summary = "编辑收藏夹")
    @PutMapping()
    public Result<CollectionVO> update(@Valid @RequestBody CollectionUpdateDTO dto){
        log.info("更新收藏夹: {}", dto);
        return Result.success(collectionService.update(dto));
    }

    @Operation(summary = "删除收藏夹(及其中所有帖子)")
    @DeleteMapping("/{uuid}")
    public Result<String> delete(@PathVariable("uuid") String uuid){
        log.info("删除收藏夹: {}", uuid);
        collectionService.delete(uuid);
        return Result.success();
    }

    @Operation(summary = "获取当前用户收藏夹列表")
    @GetMapping()
    public Result<List<CollectionVO>> collectionList(){
        log.info("获取用户uuid={}的收藏夹列表", BaseContext.getCurrentUuid());
        return Result.success(collectionService.collectionList(BaseContext.getCurrentUuid()));
    }
    @Operation(summary = "收藏攻略到指定收藏夹")
    @PostMapping("/save")
    public Result<String> saveInto(@Valid @RequestBody GuideSavedDTO guideSavedDTO){
        log.info("把帖子放入收藏夹:{}", guideSavedDTO);
        collectionService.saveInto(guideSavedDTO);
        return Result.success();
    }

    /**
     * guideUuid作为路径参数还是请求体参数更好?
     */
    @Operation(summary = "从收藏夹移除帖子")
    @DeleteMapping("/{uuid}/items")
    public Result<String> removeFrom(@PathVariable("uuid") String collectionUuid, @Valid @RequestBody String guideUuid){
        log.info("把uuid={}的帖子移出收藏夹{}", guideUuid, collectionUuid);
        collectionService.removeFrom(collectionUuid, guideUuid);
        return Result.success();
    }

    @Operation(summary = "获取某收藏夹内的攻略列表")
    @GetMapping("/{uuid}/items")
    public Result<List<GuideVO>> guideList(@PathVariable("uuid") String collectionUuid){
        return Result.success(collectionService.guideList(collectionUuid, BaseContext.getCurrentUuid()));
    }

    @Operation(summary = "查询某攻略被当前用户收藏到哪些收藏夹")
    @GetMapping("/items/check?guideUuid={uuid}")
    public Result<List<Collection>> folders(@PathVariable("uuid") String guideUuid){
        return Result.success(collectionService.inWhichGuideList(guideUuid, BaseContext.getCurrentUuid()));
    }
}
