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

    /**
     * 手动触发攻略向量化（加入 AI 知识库）。
     *
     * <p>适用场景：
     * <ul>
     *   <li>旧数据（已发布但 aiStatus 为 null）</li>
     *   <li>之前索引失败（aiStatus = 3）需要重试</li>
     * </ul>
     * 仅已发布（status=1）的攻略可触发索引，草稿调用时抛出 PARAM_INVALID。
     *
     * @param userUuid  当前用户 UUID（权限校验）
     * @param guideUuid 目标攻略 UUID
     * @return 更新后的攻略 VO（aiStatus 已重置为 PENDING）
     */
    GuideVO triggerIndex(String userUuid, String guideUuid);
}
