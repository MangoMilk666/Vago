package com.vago.travel.service.impl;

import cn.hutool.core.util.IdUtil;
import com.vago.context.BaseContext;
import com.vago.travel.mapper.CollectionMapper;
import com.vago.travel.mapper.GuideMapper;
import com.vago.travel.model.dto.CollectionCreateDTO;
import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.dto.GuideSavedDTO;
import com.vago.travel.model.entity.Collection;
import com.vago.travel.model.entity.CollectionItem;
import com.vago.travel.model.vo.CollectionVO;
import com.vago.travel.model.vo.GuideVO;
import com.vago.travel.service.CollectionService;
import com.vago.travel.service.GuideService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

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
        collectionMapper.update(dto);
        Collection c = collectionMapper.getByUuid(dto.getUuid());
        CollectionVO vo = new CollectionVO();
        BeanUtils.copyProperties(c, vo);
        return vo;
    }

    @Override
    public void delete(String uuid) {
        collectionMapper.deleteByCollection(uuid);
        collectionMapper.deleteByUuid(uuid);
    }

    @Override
    public List<CollectionVO> collectionList(String userUuid) {
        return collectionMapper.getListByUserid(userUuid);
    }

    @Override
    public void saveInto(GuideSavedDTO guideSavedDTO) {
        CollectionItem item = CollectionItem.builder().
                                uuid(IdUtil.fastSimpleUUID()).
                                collectionUuid(guideSavedDTO.getCollectionUuid()).
                                guideUuid(guideSavedDTO.getGuideUuid()).
                                userUuid(BaseContext.getCurrentUuid()).
                                note(guideSavedDTO.getNote()).
                                createdAt(LocalDateTime.now()).
                                build();
        collectionMapper.saveInto(item);
    }

    @Override
    public void removeFrom(String collectionUuid, String guideUuid) {
        collectionMapper.deleteItem(collectionUuid, guideUuid);
    }

    @Override
    public List<GuideVO> guideList(String collectionUuid, String userUuid) {
        List<String> guideIds = collectionMapper.getItemsByCollectionId(collectionUuid);
        List<GuideVO> guideVOList = new ArrayList<>();
        for (String guideId : guideIds) {
            guideVOList.add(guideService.getDetail(userUuid, guideId));
        }
        return guideVOList;
    }

    @Override
    public List<Collection> inWhichGuideList(String guideUuid, String userUuid) {
        List<String> collectionIds = collectionMapper.inWhichCollections(guideUuid, userUuid);
        List<Collection> collectionVOList = new ArrayList<>();
        for (String collectionId : collectionIds) {
            collectionVOList.add(collectionMapper.getByUuid(collectionId));
        }
        return collectionVOList;
    }
}
