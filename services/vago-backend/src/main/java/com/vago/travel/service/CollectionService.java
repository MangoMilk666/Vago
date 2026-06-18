package com.vago.travel.service;

import com.vago.travel.model.dto.CollectionCreateDTO;
import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.dto.GuideSavedDTO;
import com.vago.travel.model.entity.Collection;
import com.vago.travel.model.vo.GuideVO;
import jakarta.validation.Valid;

import java.util.List;

public interface CollectionService {

    /** 创建收藏夹 */
    Collection create(String userUuid, CollectionCreateDTO dto);

    /** 更新收藏夹（名称、描述） */
    Collection update(CollectionUpdateDTO dto);

    /**
     * 删除收藏夹（含内部所有收藏记录）。
     * 校验 owner：只有收藏夹所属用户可删除。
     */
    void delete(String uuid, String userUuid);

    /** 获取当前用户的所有收藏夹列表（按创建时间降序） */
    List<Collection> collectionList(String userUuid);

    /**
     * 收藏攻略到指定收藏夹。
     * 校验 owner + 防重复 + 校验攻略存在。
     */
    void saveInto(GuideSavedDTO dto, String userUuid);

    /**
     * 从收藏夹移除攻略。
     * 校验 owner。
     */
    void removeFrom(String collectionUuid, String guideUuid, String userUuid);

    /** 获取某收藏夹内的攻略列表（批量查询，按收藏时间降序） */
    List<GuideVO> guideList(String collectionUuid, String userUuid);

    /** 查询某攻略被当前用户收藏到了哪些收藏夹 */
    List<Collection> inWhichGuideList(String guideUuid, String userUuid);
}
