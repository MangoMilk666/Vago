package com.vago.travel.service.impl;

import cn.hutool.core.util.IdUtil;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;
import com.vago.travel.mapper.ItineraryDayMapper;
import com.vago.travel.mapper.ItinerarySpotMapper;
import com.vago.travel.mapper.PlanMapper;
import com.vago.travel.mapper.TripMapper;
import com.vago.travel.model.dto.ItineraryDayUpdateDTO;
import com.vago.travel.model.dto.ItinerarySpotDTO;
import com.vago.travel.model.entity.ItineraryDay;
import com.vago.travel.model.entity.ItinerarySpot;
import com.vago.travel.model.entity.Plan;
import com.vago.travel.model.entity.Trip;
import com.vago.travel.model.vo.ItineraryDayVO;
import com.vago.travel.model.vo.ItinerarySpotVO;
import com.vago.travel.service.ItineraryService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
@Slf4j
public class ItineraryServiceImpl implements ItineraryService {

    @Autowired private ItineraryDayMapper  dayMapper;
    @Autowired private ItinerarySpotMapper spotMapper;
    @Autowired private TripMapper          tripMapper;
    @Autowired private PlanMapper          planMapper;

    // ══════════════════════════════════════════════════════════════════════════
    // 获取全部每日行程（懒初始化）
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    @Transactional(rollbackFor = Exception.class)
    public List<ItineraryDayVO> getDays(String refUuid, int refType) {
        // 1. 解析该行程/计划的日期区间
        DateRange range = resolveDateRange(refUuid, refType);
        if (range == null) {
            // 计划尚未填写日期，返回空
            return Collections.emptyList();
        }

        // 2. 查询已有 day 记录，按 dayDate 分组
        //    同一日期现在允许多条（已移除 uk_day_ref_date 唯一约束）记录，
        //    因此使用 groupingBy 代替 toMap，避免 IllegalStateException
        List<ItineraryDay> existingDays = dayMapper.listByRef(refUuid, refType);
        Map<LocalDate, List<ItineraryDay>> daysByDate = existingDays.stream()
                .collect(Collectors.groupingBy(ItineraryDay::getDayDate));

        // 3. 懒初始化：遍历日期区间，对完全缺失的日期创建一条空记录；
        //    已有记录的日期（含多条）全部保留，并修正 dayIndex
        List<LocalDate> dates = range.toDateList();
        List<ItineraryDay> allDays = new ArrayList<>();
        for (int i = 0; i < dates.size(); i++) {
            LocalDate date   = dates.get(i);
            int expectedIndex = i + 1;
            List<ItineraryDay> daysForDate = daysByDate.getOrDefault(date, Collections.emptyList());

            if (daysForDate.isEmpty()) {
                // 该日期无任何记录，懒初始化一条空记录
                allDays.add(createEmptyDay(refUuid, refType, date, expectedIndex));
            } else {
                // 同步 dayIndex（日期区间调整后修正）
                for (ItineraryDay d : daysForDate) {
                    if (!Objects.equals(d.getDayIndex(), expectedIndex)) {
                        d.setDayIndex(expectedIndex);
                        dayMapper.update(d);
                    }
                }
                allDays.addAll(daysForDate);
            }
        }

        // 4. 一次性批量查所有景点，避免 N+1
        List<ItinerarySpot> allSpots = spotMapper.listByRef(refUuid, refType);
        Map<String, List<ItinerarySpot>> spotsByDayUuid = allSpots.stream()
                .collect(Collectors.groupingBy(ItinerarySpot::getDayUuid));

        // 5. 组装 VO
        return allDays.stream()
                .map(d -> toDayVO(d, spotsByDayUuid.getOrDefault(d.getUuid(), Collections.emptyList())))
                .collect(Collectors.toList());
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 更新单日行程
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ItineraryDayVO updateDay(String refUuid, int refType, int dayIndex,
                                    ItineraryDayUpdateDTO dto) {
        // 先确保 days 已初始化
        getDays(refUuid, refType);

        ItineraryDay day = dayMapper.getByRefAndIndex(refUuid, refType, dayIndex);
        if (day == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND);
        }

        // 更新 day 字段（null 不覆盖）
        if (dto.getTransportation() != null) day.setTransportation(dto.getTransportation());
        if (dto.getAccommodation()  != null) day.setAccommodation(dto.getAccommodation());
        if (dto.getMealBreakfast()  != null) day.setMealBreakfast(dto.getMealBreakfast());
        if (dto.getMealLunch()      != null) day.setMealLunch(dto.getMealLunch());
        if (dto.getMealDinner()     != null) day.setMealDinner(dto.getMealDinner());
        if (dto.getBudgetDay()      != null) day.setBudgetDay(dto.getBudgetDay());
        if (dto.getNotes()          != null) day.setNotes(dto.getNotes());
        dayMapper.update(day);

        // 景点全量替换（spots == null 表示不动）
        List<ItinerarySpot> savedSpots = new ArrayList<>();
        if (dto.getSpots() != null) {
            spotMapper.deleteByDay(day.getUuid());
            LocalDateTime now = LocalDateTime.now();
            for (int i = 0; i < dto.getSpots().size(); i++) {
                ItinerarySpotDTO sDTO = dto.getSpots().get(i);
                ItinerarySpot spot = ItinerarySpot.builder()
                        .uuid(IdUtil.fastSimpleUUID())
                        .dayUuid(day.getUuid())
                        .name(sDTO.getName())
                        .address(sDTO.getAddress())
                        .category(sDTO.getCategory() != null ? sDTO.getCategory() : 0)
                        .sortOrder(i)   // 以列表顺序为准，忽略客户端传来的 sortOrder
                        .durationMinutes(sDTO.getDurationMinutes())
                        .notes(sDTO.getNotes())
                        .createdAt(now)
                        .updatedAt(now)
                        .build();
                spotMapper.insert(spot);
                savedSpots.add(spot);
            }
        } else {
            savedSpots = spotMapper.listByDay(day.getUuid());
        }

        log.info("每日行程更新: refUuid={}, dayIndex={}", refUuid, dayIndex);
        return toDayVO(day, savedSpots);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // plan → trip 日程复制
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void copyDaysFromPlanToTrip(String planUuid, String tripUuid) {
        List<ItineraryDay> planDays = dayMapper.listForCopy(planUuid, ItineraryDay.REF_TYPE_PLAN);
        if (planDays.isEmpty()) return;

        LocalDateTime now = LocalDateTime.now();

        for (ItineraryDay planDay : planDays) {
            // 复制 day
            ItineraryDay tripDay = ItineraryDay.builder()
                    .uuid(IdUtil.fastSimpleUUID())
                    .refUuid(tripUuid)
                    .refType(ItineraryDay.REF_TYPE_TRIP)
                    .dayDate(planDay.getDayDate())
                    .dayIndex(planDay.getDayIndex())
                    .transportation(planDay.getTransportation())
                    .accommodation(planDay.getAccommodation())
                    .mealBreakfast(planDay.getMealBreakfast())
                    .mealLunch(planDay.getMealLunch())
                    .mealDinner(planDay.getMealDinner())
                    .budgetDay(planDay.getBudgetDay())
                    .notes(planDay.getNotes())
                    .createdAt(now)
                    .updatedAt(now)
                    .build();
            dayMapper.insert(tripDay);

            // 复制该天的景点
            List<ItinerarySpot> planSpots = spotMapper.listByDay(planDay.getUuid());
            for (ItinerarySpot ps : planSpots) {
                ItinerarySpot ts = ItinerarySpot.builder()
                        .uuid(IdUtil.fastSimpleUUID())
                        .dayUuid(tripDay.getUuid())
                        .name(ps.getName())
                        .address(ps.getAddress())
                        .category(ps.getCategory())
                        .sortOrder(ps.getSortOrder())
                        .durationMinutes(ps.getDurationMinutes())
                        .notes(ps.getNotes())
                        .createdAt(now)
                        .updatedAt(now)
                        .build();
                spotMapper.insert(ts);
            }
        }
        log.info("计划日程已复制到行程: planUuid={} → tripUuid={}, days={}",
                planUuid, tripUuid, planDays.size());
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 私有工具方法
    // ══════════════════════════════════════════════════════════════════════════

    /** 创建空的 day 记录并持久化 */
    private ItineraryDay createEmptyDay(String refUuid, int refType,
                                         LocalDate dayDate, int dayIndex) {
        LocalDateTime now = LocalDateTime.now();
        ItineraryDay day = ItineraryDay.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .refUuid(refUuid)
                .refType(refType)
                .dayDate(dayDate)
                .dayIndex(dayIndex)
                .createdAt(now)
                .updatedAt(now)
                .build();
        dayMapper.insert(day);
        return day;
    }

    /** 根据 refType 查询日期区间 */
    private DateRange resolveDateRange(String refUuid, int refType) {
        if (refType == ItineraryDay.REF_TYPE_TRIP) {
            Trip trip = tripMapper.getByUuid(refUuid);
            if (trip == null || trip.getStartDate() == null || trip.getEndDate() == null) {
                return null;
            }
            return new DateRange(trip.getStartDate(), trip.getEndDate());
        } else {
            Plan plan = planMapper.getByUuid(refUuid);
            if (plan == null || plan.getStartDate() == null || plan.getEndDate() == null) {
                return null;
            }
            return new DateRange(plan.getStartDate(), plan.getEndDate());
        }
    }

    /** ItineraryDay + spots → VO */
    private ItineraryDayVO toDayVO(ItineraryDay d, List<ItinerarySpot> spots) {
        return ItineraryDayVO.builder()
                .uuid(d.getUuid())
                .dayDate(d.getDayDate())
                .dayIndex(d.getDayIndex())
                .transportation(d.getTransportation())
                .accommodation(d.getAccommodation())
                .mealBreakfast(d.getMealBreakfast())
                .mealLunch(d.getMealLunch())
                .mealDinner(d.getMealDinner())
                .budgetDay(d.getBudgetDay())
                .notes(d.getNotes())
                .spots(spots.stream().map(this::toSpotVO).collect(Collectors.toList()))
                .build();
    }

    private ItinerarySpotVO toSpotVO(ItinerarySpot s) {
        return ItinerarySpotVO.builder()
                .uuid(s.getUuid())
                .name(s.getName())
                .address(s.getAddress())
                .category(s.getCategory())
                .sortOrder(s.getSortOrder())
                .durationMinutes(s.getDurationMinutes())
                .notes(s.getNotes())
                .build();
    }

    // ── 日期区间辅助 ──────────────────────────────────────────────────────────

    private static class DateRange {
        final LocalDate start;
        final LocalDate end;

        DateRange(LocalDate start, LocalDate end) {
            this.start = start;
            this.end   = end;
        }

        /** 返回 [start, end] 之间所有日期（含两端） */
        List<LocalDate> toDateList() {
            List<LocalDate> list = new ArrayList<>();
            LocalDate cur = start;
            while (!cur.isAfter(end)) {
                list.add(cur);
                cur = cur.plusDays(1);
            }
            return list;
        }
    }
}
