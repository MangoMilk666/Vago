package com.vago.travel.service;

import com.vago.travel.model.dto.CollectionCreateDTO;
import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.dto.GuideSavedDTO;
import com.vago.travel.model.entity.Collection;
import com.vago.travel.model.vo.CollectionVO;
import com.vago.travel.model.vo.GuideVO;
import jakarta.validation.Valid;

import java.util.List;

public interface CollectionService {

    /**
     * 创建收藏夹
     */
    CollectionVO create(String currentUuid, @Valid CollectionCreateDTO dto);

    /**
     * 更新收藏夹
     */
    CollectionVO update(@Valid CollectionUpdateDTO dto);

    /**
     * 删除收藏夹
     */
    void delete(String uuid);

    /**
     * 获取当前用户收藏夹列表
     */
    List<CollectionVO> collectionList(String userUuid);


    /**
     * 从收藏夹移除帖子
     */
    void removeFrom(String collectionUuid, @Valid String guideUuid);

    /**
     * 获取某收藏夹内的攻略列表
     */
    List<GuideVO> guideList(String collectionUuid, String userUuid);

    /**
     * 查询某攻略被当前用户收藏到哪些收藏夹
     */
    List<Collection> inWhichGuideList(String guideUuid, String userUuid);

    /**
     * 收藏帖子
     */
    void saveInto(@Valid GuideSavedDTO guideSavedDTO);
}
