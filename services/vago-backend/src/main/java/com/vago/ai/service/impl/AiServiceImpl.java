package com.vago.ai.service.impl;

import com.vago.ai.client.VagoAiClient;
import com.vago.ai.model.dto.AiChatRequestDTO;
import com.vago.ai.model.vo.AiChatResponseVO;
import com.vago.ai.service.AiService;
import com.vago.travel.mapper.GuideMapper;
import com.vago.travel.model.entity.Guide;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

/**
 * AI 集成服务实现。
 *
 * <p>indexGuideAsync / deleteGuideAsync 使用 @Async 注解，
 * 运行在 Spring 默认异步线程池中，不阻塞 GuideService 的主线程。
 * 线程池由 @EnableAsync（定义于 AiClientConfig）激活。
 *
 * <p>chat / chatStream 为同步/响应式调用，直接委托给 VagoAiClient。
 */
@Service
@Slf4j
public class AiServiceImpl implements AiService {

    /** AI 向量化状态常量（与 Guide.aiStatus 字段语义一致） */
    private static final int AI_STATUS_INDEXING = 1;
    private static final int AI_STATUS_INDEXED  = 2;
    private static final int AI_STATUS_FAILED   = 3;

    @Autowired
    private VagoAiClient vagoAiClient;

    /**
     * GuideMapper 用于异步任务完成后回写 ai_status 字段。
     * AiServiceImpl 不执行任何 Guide 业务逻辑，仅更新状态字段。
     */
    @Autowired
    private GuideMapper guideMapper;

    /**
     * 异步执行攻略向量化全流程。
     *
     * <p>执行顺序：
     * <ol>
     *   <li>将 ai_status 置为 INDEXING（1）</li>
     *   <li>调用 VagoAiClient.ingestGuide → Python /api/v1/articles/ingest</li>
     *   <li>成功 → INDEXED（2）；失败 → FAILED（3）</li>
     * </ol>
     *
     * <p>任何异常均在此处捕获，不向上传播（避免 @Async 线程静默死亡）。
     */
    @Override
    @Async
    public void indexGuideAsync(Guide guide) {
        String uuid = guide.getUuid();
        log.info("[AiService] 开始向量化 guide={} user={}", uuid, guide.getUserUuid());
        // ai_status字段更新为“向量化中...”
        guideMapper.updateAiStatus(uuid, AI_STATUS_INDEXING);

        try {
            VagoAiClient.IngestResponse resp = vagoAiClient.ingestGuide(
                    uuid,
                    guide.getUserUuid(),
                    guide.getTitle(),
                    guide.getContent(),
                    guide.getDestination()
            );

            if ("INDEXED".equals(resp.getStatus())) {
                guideMapper.updateAiStatus(uuid, AI_STATUS_INDEXED);
                log.info("[AiService] 向量化成功 guide={} chunks={}", uuid, resp.getChunkCount());
            } else {
                guideMapper.updateAiStatus(uuid, AI_STATUS_FAILED);
                log.warn("[AiService] 向量化失败 guide={} reason={}", uuid, resp.getMessage());
            }
        } catch (Exception e) {
            guideMapper.updateAiStatus(uuid, AI_STATUS_FAILED);
            log.error("[AiService] 向量化异常 guide={} error={}", uuid, e.getMessage(), e);
        }
    }

    /**
     * 异步删除攻略向量数据。异步指相对java主业务线程异步，底层网络通信层（WebClient 调用 Python 向量数据库端）实际同步阻塞
     *
     * <p>删除失败仅记录日志，不抛出异常，不影响 Guide 的软删除主流程。
     */
    @Override
    @Async
    public void deleteGuideAsync(String guideUuid, String userUuid) {
        log.info("[AiService] 删除向量数据 guide={} user={}", guideUuid, userUuid);
        try {
            vagoAiClient.deleteGuide(guideUuid, userUuid);
            log.info("[AiService] 向量删除成功 guide={}", guideUuid);
        } catch (Exception e) {
            log.error("[AiService] 向量删除失败 guide={} error={}", guideUuid, e.getMessage(), e);
        }
    }

    /**
     * 同步非流式对话，直接委托给 VagoAiClient。
     * 若 vago-ai 不可用，VagoAiClient 内部抛出 RuntimeException，
     * 由 GlobalExceptionHandler 统一处理为 5031 响应。
     */
    @Override
    public AiChatResponseVO chat(AiChatRequestDTO dto, String userUuid) {
        return vagoAiClient.chat(dto.getMessages(), userUuid);
    }

    /**
     * 流式对话，返回 Flux 供 AiController 订阅代理。
     * Flux 懒加载，此处不发起 HTTP 请求。
     */
    @Override
    public Flux<ServerSentEvent<String>> chatStream(AiChatRequestDTO dto, String userUuid) {
        // Flux：异步流式数据的响应管道
        return vagoAiClient.chatStream(dto.getMessages(), userUuid);
    }
}
