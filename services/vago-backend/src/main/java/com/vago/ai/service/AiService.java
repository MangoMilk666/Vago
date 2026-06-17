package com.vago.ai.service;

import com.vago.ai.model.dto.AiPlanSaveDTO;
import com.vago.ai.model.vo.AiPlanSaveVO;
import com.vago.travel.model.entity.Guide;

/**
 * AI 集成服务接口。
 *
 * <p>负责两类职责：
 * <ol>
 *   <li>攻略向量化生命周期管理（index / delete），由 GuideService 的增删改事件触发。</li>
 *   <li>AI 行程保存，将 AI 生成的结构化行程持久化到 MySQL（plans / trips）。</li>
 * </ol>
 *
 * <p>AI 对话推理（chat / chatStream）已重构为前端直连 Python vago-ai，
 * Java 不再作为 SSE 代理，对应方法已从本接口移除。
 */
public interface AiService {

    /**
     * 异步将攻略向量化并写入 Qdrant（fire-and-forget）。
     *
     * @param guide 已持久化的攻略实体（uuid、content、userUuid 必须非空）
     */
    void indexGuideAsync(Guide guide);

    /**
     * 异步从 Qdrant 删除攻略的向量数据（fire-and-forget）。
     *
     * @param guideUuid 攻略 UUID
     * @param userUuid  归属用户 UUID（用于安全校验）
     */
    void deleteGuideAsync(String guideUuid, String userUuid);

    /**
     * 将 AI 生成的结构化行程保存为计划草稿。
     */
    AiPlanSaveVO saveAsDraft(AiPlanSaveDTO dto, String userUuid);

    /**
     * 将 AI 生成的结构化行程保存为正式行程。
     * 要求 startDate 和 endDate 非空。
     */
    AiPlanSaveVO saveAsTrip(AiPlanSaveDTO dto, String userUuid);
}
