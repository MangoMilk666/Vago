package com.vago.travel.service.impl;

import cn.hutool.core.util.IdUtil;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;
import com.vago.travel.mapper.CollectionMapper;
import com.vago.travel.mapper.GuideMapper;
import com.vago.travel.model.dto.CollectionCreateDTO;
import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.dto.GuideSavedDTO;
import com.vago.travel.model.entity.Collection;
import com.vago.travel.model.entity.CollectionItem;
import com.vago.travel.model.entity.Guide;
import com.vago.travel.model.vo.CollectionVO;
import com.vago.travel.model.vo.GuideVO;
import com.vago.travel.service.CollectionService;
import com.vago.travel.service.GuideService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

@Service
@Slf4j
public class CollectionServiceImpl implements CollectionService {

    @Autowired
    private CollectionMapper collectionMapper;
    @Autowired
    private GuideMapper guideMapper;
    @Autowired
    private GuideService guideService;

    @Override
    public CollectionVO create(String currentUuid, CollectionCreateDTO dto) {
        LocalDateTime now = LocalDateTime.now();
        CollectionVO collectionVO = CollectionVO.builder().
                                    uuid(IdUtil.fastSimpleUUID()).
                                    userUuid(currentUuid).
                                    name(dto.getName()).
                                    type(1).
                                    description(dto.getDescription()).
                                    createdAt(now).
                                    updatedAt(now).
                                    build();

        Collection collection = new Collection();
        BeanUtils.copyProperties(collectionVO, collection);
        collectionMapper.insert(collection);
        return collectionVO;
    }

    @Override
    public CollectionVO update(CollectionUpdateDTO dto) {
        // 校验：收藏夹存在且属于当前用户
        Collection c = collectionMapper.getByUuid(dto.getUuid());
        if (c == null) {
            throw new BusinessException(ResultCode.COLLECTION_NOT_FOUND);
        }

        collectionMapper.update(dto);
        Collection updated = collectionMapper.getByUuid(dto.getUuid());
        return toVO(updated);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String uuid, String userUuid) {
        // 校验：收藏夹存在且属于当前用户
        Collection c = collectionMapper.getByUuid(uuid);
        if (c == null) {
            throw new BusinessException(ResultCode.COLLECTION_NOT_FOUND);
        }
        if (!c.getUserUuid().equals(userUuid)) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }

        // 先删除收藏夹内的所有收藏记录，再删除收藏夹本身
        collectionMapper.deleteItemsByCollection(uuid);
        collectionMapper.deleteByUuid(uuid);
        log.info("删除收藏夹: uuid={} user={}", uuid, userUuid);
    }

    @Override
    public List<Collection> collectionList(String userUuid) {
        List<Collection> collectionList = collectionMapper.getListByUserid(userUuid);
        return collectionList;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveInto(GuideSavedDTO dto, String userUuid) {
        // 1. 校验收藏夹存在且属于当前用户
        Collection c = collectionMapper.getByUuid(dto.getCollectionUuid());
        if (c == null) {
            throw new BusinessException(ResultCode.COLLECTION_NOT_FOUND);
        }
        if (!c.getUserUuid().equals(userUuid)) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }

        // 2. 校验攻略存在
        Guide guide = guideMapper.getByUuid(dto.getGuideUuid());
        if (guide == null) {
            throw new BusinessException(ResultCode.GUIDE_NOT_FOUND);
        }

        // 3. 防重复：同一收藏夹不能重复收藏同一篇攻略
        if (collectionMapper.countItem(dto.getCollectionUuid(), dto.getGuideUuid()) > 0) {
            log.warn("重复收藏: collection={} guide={} user={}",
                    dto.getCollectionUuid(), dto.getGuideUuid(), userUuid);
            throw new BusinessException(ResultCode.COLLECTION_ITEM_EXISTS);
        }

        // 4. 写入收藏记录
        CollectionItem item = CollectionItem.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .collectionUuid(dto.getCollectionUuid())
                .guideUuid(dto.getGuideUuid())
                .userUuid(userUuid)
                .note(dto.getNote())
                .createdAt(LocalDateTime.now())
                .build();
        collectionMapper.saveInto(item);
        log.info("收藏成功: collection={} guide={} user={}",
                dto.getCollectionUuid(), dto.getGuideUuid(), userUuid);
    }

    @Override
    public void removeFrom(String collectionUuid, String guideUuid, String userUuid) {
        // 校验：收藏夹存在且属于当前用户
        Collection c = collectionMapper.getByUuid(collectionUuid);
        if (c == null) {
            throw new BusinessException(ResultCode.COLLECTION_NOT_FOUND);
        }
        if (!c.getUserUuid().equals(userUuid)) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }

        collectionMapper.deleteItem(collectionUuid, guideUuid);
        log.info("移除收藏: collection={} guide={} user={}", collectionUuid, guideUuid, userUuid);
    }

    @Override
    public List<GuideVO> guideList(String collectionUuid, String userUuid) {
        // 1. 校验收藏夹存在
        Collection c = collectionMapper.getByUuid(collectionUuid);
        if (c == null) {
            throw new BusinessException(ResultCode.COLLECTION_NOT_FOUND);
        }

        // 2. 批量查出所有 guide UUID
        List<String> guideIds = collectionMapper.getItemsByCollectionId(collectionUuid);
        if (guideIds.isEmpty()) {
            return Collections.emptyList();
        }

        // 3. 批量查询攻略 VO（使用 GuideService.listByIds 避免 N+1）
        return guideService.listByIds(userUuid, guideIds);
    }

    @Override
    public List<CollectionVO> inWhichGuideList(String guideUuid, String userUuid) {
        List<String> collectionIds = collectionMapper.inWhichCollections(guideUuid, userUuid);
        if (collectionIds.isEmpty()) {
            return Collections.emptyList();
        }
        return collectionIds.stream()
                .map(id -> collectionMapper.getByUuid(id))
                .map(this::toVO)
                .collect(Collectors.toList());
    }

    // ── 私有工具 ───────────────────────────────────────────────────────────────

    /** Collection 实体 → CollectionVO */
    private CollectionVO toVO(Collection c) {
        if (c == null) return null;
        CollectionVO vo = new CollectionVO();
        BeanUtils.copyProperties(c, vo);
        return vo;
    }
}
