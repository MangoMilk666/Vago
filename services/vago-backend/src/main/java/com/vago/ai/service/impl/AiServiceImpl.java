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

import cn.hutool.core.util.IdUtil;
import com.vago.ai.model.dto.AiPlanSaveDTO;
import com.vago.ai.model.vo.AiPlanSaveVO;
import com.vago.travel.mapper.ItineraryDayMapper;
import com.vago.travel.mapper.ItinerarySpotMapper;
import com.vago.travel.mapper.PlanMapper;
import com.vago.travel.mapper.TripMapper;
import com.vago.travel.model.entity.ItineraryDay;
import com.vago.travel.model.entity.ItinerarySpot;
import com.vago.travel.model.entity.Plan;
import com.vago.travel.model.entity.Trip;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;

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

    @Autowired
    private PlanMapper planMapper;

    @Autowired
    private TripMapper tripMapper;

    @Autowired
    private ItineraryDayMapper dayMapper;

    @Autowired
    private ItinerarySpotMapper spotMapper;

    /**
     * 异步执行攻略向量化全流程。
     *
     * <p>执行顺序：
     * <ol>
     *   <li>将 ai_status 置为 INDEXING（1）</li>
     *   <li>调用 VagoAiClient.ingestGuide → Python /api/v1/articles/ingest</li>
     *   <li>成功：ai_status 置为 INDEXED（2）</li>
     *   <li>失败：ai_status 置为 FAILED（3）</li>
     * </ol>
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

    // ── AI 结构化行程保存 ─────────────────────────────────────────────────────
    /**
     * 将 AI 生成的结构化行程保存为计划草稿。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public AiPlanSaveVO saveAsDraft(AiPlanSaveDTO dto, String userUuid) {
        log.info("[AiService] 保存AI行程为草稿 user={} title={}", userUuid, dto.getTitle());

        // 1. 创建 Plan
        LocalDateTime now = LocalDateTime.now();
        Plan plan = Plan.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .userUuid(userUuid)
                .title(dto.getTitle())
                .destination(dto.getDestination())
                .startDate(parseDate(dto.getStartDate()))
                .endDate(parseDate(dto.getEndDate()))
                .budget(dto.getBudget())
                .budgetCurrency(dto.getBudgetCurrency() != null ? dto.getBudgetCurrency() : "CNY")
                .status(0)  // 0-草稿，1-已转换
                .createdAt(now)
                .updatedAt(now)
                .build();
        planMapper.insert(plan);

        // 2. 创建 ItineraryDays + Spots，类型是Plan
        createDaysAndSpots(plan.getUuid(), ItineraryDay.REF_TYPE_PLAN, dto.getDays(), now);

        log.info("[AiService] 草稿保存成功 planUuid={} days={}", plan.getUuid(), dto.getDays().size());
        return AiPlanSaveVO.builder().uuid(plan.getUuid()).type("plan").build();
    }

    /**
     * 将 AI 生成的结构化行程保存为正式行程。
     * 要求 startDate 和 endDate 非空。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public AiPlanSaveVO saveAsTrip(AiPlanSaveDTO dto, String userUuid) {
        log.info("[AiService] 保存AI行程为正式行程 user={} title={}", userUuid, dto.getTitle());

        // 校验日期必填
        LocalDate startDate = parseDate(dto.getStartDate());
        LocalDate endDate = parseDate(dto.getEndDate());
        if (startDate == null || endDate == null) {
            throw new BusinessException(ResultCode.PARAM_INVALID);
        }

        // 1. 创建 Trip
        LocalDateTime now = LocalDateTime.now();
        Trip trip = Trip.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .userUuid(userUuid)
                .title(dto.getTitle())
                .destination(dto.getDestination())
                .startDate(startDate)
                .endDate(endDate)
                .status(1)  // 行程类型，1-计划中，2-已完成，3-已取消
                .createdAt(now)
                .updatedAt(now)
                .build();
        // 插入表trips
        tripMapper.insert(trip);

        // 2. 创建 ItineraryDays + Spots
        createDaysAndSpots(trip.getUuid(), ItineraryDay.REF_TYPE_TRIP, dto.getDays(), now);

        log.info("[AiService] 行程保存成功 tripUuid={} days={}", trip.getUuid(), dto.getDays().size());
        return AiPlanSaveVO.builder().uuid(trip.getUuid()).type("trip").build();
    }

    /**
     * 批量创建每日行程和景点记录。
     * 复用逻辑：save-draft 和 save-trip 共享。
     */
    private void createDaysAndSpots(String refUuid, int refType,
                                     List<AiPlanSaveDTO.AiDayDTO> days, LocalDateTime now) {
        for (AiPlanSaveDTO.AiDayDTO dayDto : days) {
            ItineraryDay day = ItineraryDay.builder()
                    .uuid(IdUtil.fastSimpleUUID())
                    .refUuid(refUuid)
                    .refType(refType)
                    .dayDate(parseDate(dayDto.getDayDate()))
                    .dayIndex(dayDto.getDayIndex())
                    .transportation(dayDto.getTransportation())
                    .accommodation(dayDto.getAccommodation())
                    .mealBreakfast(dayDto.getMealBreakfast())
                    .mealLunch(dayDto.getMealLunch())
                    .mealDinner(dayDto.getMealDinner())
                    .budgetDay(dayDto.getBudgetDay())
                    .notes(dayDto.getNotes())
                    .createdAt(now)
                    .updatedAt(now)
                    .build();
            // 插入表itinerary_days
            dayMapper.insert(day);

            // 景点
            if (dayDto.getSpots() != null) {
                for (int i = 0; i < dayDto.getSpots().size(); i++) {
                    AiPlanSaveDTO.AiSpotDTO spotDto = dayDto.getSpots().get(i);
                    ItinerarySpot spot = ItinerarySpot.builder()
                            .uuid(IdUtil.fastSimpleUUID())
                            .dayUuid(day.getUuid())
                            .name(spotDto.getName())
                            .address(spotDto.getAddress())
                            .category(spotDto.getCategory() != null ? spotDto.getCategory() : 0)
                            .sortOrder(i)
                            .durationMinutes(spotDto.getDurationMinutes())
                            .notes(spotDto.getNotes())
                            .createdAt(now)
                            .updatedAt(now)
                            .build();
                    // 插入表itinerary_spots
                    spotMapper.insert(spot);
                }
            }
        }
    }

    /**
     * 解析日期字符串（YYYY-MM-DD），为 null 或空则返回 null。
     */
    private LocalDate parseDate(String dateStr) {
        if (dateStr == null || dateStr.isBlank()) return null;
        try {
            return LocalDate.parse(dateStr);
        } catch (Exception e) {
            log.warn("[AiService] 日期解析失败: {}", dateStr);
            return null;
        }
    }
}
