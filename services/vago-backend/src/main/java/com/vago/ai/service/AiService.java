package com.vago.ai.service;

import com.vago.ai.model.dto.AiPlanSaveDTO;
import com.vago.ai.model.vo.AiPlanSaveVO;
import com.vago.ai.model.dto.AiChatRequestDTO;
import com.vago.ai.model.vo.AiChatResponseVO;
import com.vago.travel.model.entity.Guide;
import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;

/**
 * AI 集成服务接口。
 *
 * <p>负责两类职责：
 * <ol>
 *   <li>攻略向量化生命周期管理（index / delete），由 GuideService 的增删改事件触发。</li>
 *   <li>AI 对话代理（chat / chatStream），由 AiController 转发前端请求。</li>
 * </ol>
 */
public interface AiService {

    /**
     * 异步将攻略向量化并写入 Qdrant（fire-and-forget）。
     *
     * <p>通过 @Async 在独立线程池中执行，不阻塞调用方（GuideService）的主流程。
     * 执行过程中会将 Guide.aiStatus 依次更新为 INDEXING → INDEXED / FAILED。
     *
     * @param guide 已持久化的攻略实体（uuid、content、userUuid 必须非空）
     */
    void indexGuideAsync(Guide guide);

    /**
     * 异步从 Qdrant 删除攻略的向量数据（fire-and-forget）。
     *
     * <p>通过 @Async 在独立线程池中执行。删除失败只记录日志，不影响主流程。
     *
     * @param guideUuid 攻略 UUID
     * @param userUuid  归属用户 UUID（用于安全校验）
     */
    void deleteGuideAsync(String guideUuid, String userUuid);

    /**
     * 同步非流式 AI 对话。
     *
     * <p>阻塞等待 LangChain Agent 生成完整回答后返回，适合后台批处理场景。
     *
     * @param dto      包含完整对话历史的请求 DTO
     * @param userUuid 当前用户 UUID（用于 RAG 命名空间检索）
     * @return 回答文本 + 引用来源列表 + 模型名称
     */
    AiChatResponseVO chat(AiChatRequestDTO dto, String userUuid);

    /**
     * 流式 AI 对话，返回 SSE 事件 Flux。
     *
     * <p>由 AiController 订阅并通过 SseEmitter 代理给前端。
     * Flux 为懒加载，订阅前不发起 HTTP 请求。
     *
     * @param dto      包含完整对话历史的请求 DTO
     * @param userUuid 当前用户 UUID
     * @return SSE 事件流，data 字段为 Python vago-ai 原始 JSON 字符串
     */
    Flux<ServerSentEvent<String>> chatStream(AiChatRequestDTO dto, String userUuid);

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
