package com.vago.travel.service;

import com.vago.common.PageVO;
import com.vago.travel.model.dto.GuideCreateDTO;
import com.vago.travel.model.dto.GuideUpdateDTO;
import com.vago.travel.model.vo.GuideVO;

import java.util.List;

public interface GuideService {

    /** 公开攻略列表（分页，只返回已发布的） */
    PageVO<GuideVO> listPublished(int page, int size);

    /** 我的攻略列表（含草稿） */
    List<GuideVO> listMine(String userUuid);

    /** 查看攻略详情（浏览量 +1） */
    GuideVO getDetail(String userUuid, String guideUuid);

    /** 创建攻略 */
    GuideVO create(String userUuid, GuideCreateDTO dto);

    /** 更新攻略 */
    GuideVO update(String userUuid, String guideUuid, GuideUpdateDTO dto);

    /** 删除攻略（软删除） */
    void delete(String userUuid, String guideUuid);

    /** 点赞攻略 */
    void like(String guideUuid);
}
