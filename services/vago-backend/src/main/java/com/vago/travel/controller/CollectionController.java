package com.vago.travel.controller;

import com.vago.common.Result;
import com.vago.context.BaseContext;
import com.vago.travel.model.dto.CollectionCreateDTO;
import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.dto.GuideSavedDTO;
import com.vago.travel.model.entity.Collection;
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
    @PostMapping
    public Result<Collection> create(@Valid @RequestBody CollectionCreateDTO dto) {
        log.info("创建收藏夹: name={} type={}", dto.getName(), dto.getType());
        return Result.success(collectionService.create(BaseContext.getCurrentUuid(), dto));
    }

    @Operation(summary = "编辑收藏夹（名称/描述）")
    @PutMapping
    public Result<Collection> update(@Valid @RequestBody CollectionUpdateDTO dto) {
        log.info("更新收藏夹: uuid={} name={}", dto.getUuid(), dto.getName());
        return Result.success(collectionService.update(dto));
    }

    @Operation(summary = "删除收藏夹（含内部所有收藏记录）")
    @DeleteMapping("/{uuid}")
    public Result<String> delete(@PathVariable("uuid") String uuid) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("删除收藏夹: uuid={} user={}", uuid, userUuid);
        collectionService.delete(uuid, userUuid);
        return Result.success();
    }

    @Operation(summary = "获取当前用户的收藏夹列表")
    @GetMapping
    public Result<List<Collection>> collectionList() {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("获取收藏夹列表: user={}", userUuid);
        return Result.success(collectionService.collectionList(userUuid));
    }

    @Operation(summary = "收藏攻略到指定收藏夹")
    @PostMapping("/items")
    public Result<String> saveInto(@Valid @RequestBody GuideSavedDTO dto) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("收藏攻略: collection={} guide={} user={}",
                dto.getCollectionUuid(), dto.getGuideUuid(), userUuid);
        collectionService.saveInto(dto, userUuid);
        return Result.success();
    }

    @Operation(summary = "从收藏夹移除指定攻略")
    @DeleteMapping("/{collectionUuid}/items/{guideUuid}")
    public Result<String> removeFrom(
            @PathVariable("collectionUuid") String collectionUuid,
            @PathVariable("guideUuid") String guideUuid) {
        String userUuid = BaseContext.getCurrentUuid();
        log.info("移除收藏: collection={} guide={} user={}", collectionUuid, guideUuid, userUuid);
        collectionService.removeFrom(collectionUuid, guideUuid, userUuid);
        return Result.success();
    }

    @Operation(summary = "获取某收藏夹内的攻略列表")
    @GetMapping("/{uuid}/items")
    public Result<List<GuideVO>> guideList(@PathVariable("uuid") String collectionUuid) {
        String userUuid = BaseContext.getCurrentUuid();
        return Result.success(collectionService.guideList(collectionUuid, userUuid));
    }

    @Operation(summary = "查询某攻略被当前用户收藏到哪些收藏夹")
    @GetMapping("/items/check")
    public Result<List<Collection>> folders(@RequestParam("guideUuid") String guideUuid) {
        String userUuid = BaseContext.getCurrentUuid();
        return Result.success(collectionService.inWhichGuideList(guideUuid, userUuid));
    }
}
