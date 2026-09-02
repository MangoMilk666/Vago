package com.vago.ai.service.impl;

import com.vago.ai.service.AiService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

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
 * <p>chat / chatStream 已重构为前端直连 Python vago-ai，Java 不再代理 SSE 流。
 */
@Service
@Slf4j
public class AiServiceImpl implements AiService {

    @Autowired
    private PlanMapper planMapper;

    @Autowired
    private TripMapper tripMapper;

    @Autowired
    private ItineraryDayMapper dayMapper;

    @Autowired
    private ItinerarySpotMapper spotMapper;

    // ── AI 结构化行程保存 ─────────────────────────────────────────────────────
    /**
     * 将 AI 生成的结构化行程保存为计划草稿。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public AiPlanSaveVO saveAsDraft(AiPlanSaveDTO dto, String userUuid) {
        log.info("[AiService] 保存AI行程为草稿 user={} title={}", userUuid, dto.getTitle());

        // 1. 解析日期，如果计划草稿未给定日期，则默认以今天为起点计算出起止日期
        LocalDateTime now = LocalDateTime.now();
        LocalDate startDate = parseDate(dto.getStartDate());
        LocalDate endDate = parseDate(dto.getEndDate());
        if (startDate == null) {
            startDate = LocalDate.now();
        }
        if (endDate == null) {
            endDate = startDate.plusDays(dto.getDays().size() - 1);
        }

        Plan plan = Plan.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .userUuid(userUuid)
                .title(dto.getTitle())
                .destination(dto.getDestination())
                .startDate(startDate)
                .endDate(endDate)
                .budget(dto.getBudget())
                .budgetCurrency(dto.getBudgetCurrency() != null ? dto.getBudgetCurrency() : "CNY")
                .status(0)  // 0-草稿，1-已转换
                .createdAt(now)
                .updatedAt(now)
                .build();
        planMapper.insert(plan);

        // 2. 创建 ItineraryDays + Spots，类型是Plan
        createDaysAndSpots(plan.getUuid(), ItineraryDay.REF_TYPE_PLAN, dto.getDays(), startDate, now);

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
        createDaysAndSpots(trip.getUuid(), ItineraryDay.REF_TYPE_TRIP, dto.getDays(), startDate, now);

        log.info("[AiService] 行程保存成功 tripUuid={} days={}", trip.getUuid(), dto.getDays().size());
        return AiPlanSaveVO.builder().uuid(trip.getUuid()).type("trip").build();
    }

    /**
     * 批量创建每日行程和景点记录。
     * 复用逻辑：save-draft 和 save-trip 共享。
     */
    private void createDaysAndSpots(String refUuid, int refType,
                                     List<AiPlanSaveDTO.AiDayDTO> days, LocalDate baseStartDate, LocalDateTime now) {
        for (AiPlanSaveDTO.AiDayDTO dayDto : days) {
            // 计算 dayDate：如果 AI 没返回具体日期，以 baseStartDate 为准累加
            LocalDate dayDate = parseDate(dayDto.getDayDate());
            if (dayDate == null) {
                dayDate = baseStartDate.plusDays(dayDto.getDayIndex() - 1);
            }

            ItineraryDay day = ItineraryDay.builder()
                    .uuid(IdUtil.fastSimpleUUID())
                    .refUuid(refUuid)
                    .refType(refType)
                    .dayDate(dayDate)
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
