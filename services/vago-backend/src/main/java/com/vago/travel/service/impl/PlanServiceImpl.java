package com.vago.travel.service.impl;

import cn.hutool.core.util.IdUtil;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;
import com.vago.travel.mapper.PlanMapper;
import com.vago.travel.mapper.TripMapper;
import com.vago.travel.model.dto.PlanCreateDTO;
import com.vago.travel.model.dto.PlanUpdateDTO;
import com.vago.travel.model.entity.Plan;
import com.vago.travel.model.entity.Trip;
import com.vago.travel.model.vo.PlanVO;
import com.vago.travel.model.vo.TripVO;
import com.vago.travel.service.ItineraryService;
import com.vago.travel.service.PlanService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
@Slf4j
public class PlanServiceImpl implements PlanService {

    @Autowired
    private PlanMapper planMapper;

    @Autowired
    private TripMapper tripMapper;

    /** @Lazy 打破 PlanServiceImpl ↔ ItineraryServiceImpl 的循环依赖 */
    @Lazy
    @Autowired
    private ItineraryService itineraryService;

    @Override
    public PlanVO create(String userUuid, PlanCreateDTO dto) {
        LocalDateTime now = LocalDateTime.now();
        Plan plan = Plan.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .userUuid(userUuid)
                .title(dto.getTitle())
                .destination(dto.getDestination())
                .startDate(dto.getStartDate())
                .endDate(dto.getEndDate())
                .budget(dto.getBudget())
                .budgetCurrency(dto.getBudgetCurrency() != null ? dto.getBudgetCurrency() : "CNY")
                .notes(dto.getNotes())
                .status(0)   // 草稿
                .createdAt(now)
                .updatedAt(now)
                .build();

        planMapper.insert(plan);
        log.info("计划创建: uuid={}, userUuid={}", plan.getUuid(), userUuid);
        return toVO(plan);
    }

    @Override
    public List<PlanVO> listMyPlans(String userUuid) {
        return planMapper.listByUserUuid(userUuid)
                .stream().map(this::toVO).collect(Collectors.toList());
    }

    @Override
    public PlanVO getDetail(String userUuid, String planUuid) {
        Plan plan = getPlanOrThrow(planUuid);
        checkOwner(plan, userUuid);
        return toVO(plan);
    }

    @Override
    public PlanVO update(String userUuid, String planUuid, PlanUpdateDTO dto) {
        Plan plan = getPlanOrThrow(planUuid);
        checkOwner(plan, userUuid);

        if (dto.getTitle()          != null) plan.setTitle(dto.getTitle());
        if (dto.getDestination()    != null) plan.setDestination(dto.getDestination());
        if (dto.getStartDate()      != null) plan.setStartDate(dto.getStartDate());
        if (dto.getEndDate()        != null) plan.setEndDate(dto.getEndDate());
        if (dto.getBudget()         != null) plan.setBudget(dto.getBudget());
        if (dto.getBudgetCurrency() != null) plan.setBudgetCurrency(dto.getBudgetCurrency());
        if (dto.getNotes()          != null) plan.setNotes(dto.getNotes());

        planMapper.update(plan);
        log.info("计划更新: uuid={}", planUuid);
        return toVO(planMapper.getByUuid(planUuid));
    }

    @Override
    public void delete(String userUuid, String planUuid) {
        Plan plan = getPlanOrThrow(planUuid);
        checkOwner(plan, userUuid);
        planMapper.softDelete(planUuid);
        log.info("计划删除: uuid={}", planUuid);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public TripVO convertToTrip(String userUuid, String planUuid) {
        Plan plan = getPlanOrThrow(planUuid);
        checkOwner(plan, userUuid);

        // 已转换的计划不允许重复转换
        if (plan.getStatus() == 1) {
            throw new BusinessException(ResultCode.PLAN_ALREADY_CONVERTED);
        }

        // 用计划数据创建正式行程
        LocalDateTime now = LocalDateTime.now();
        Trip trip = Trip.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .userUuid(userUuid)
                .title(plan.getTitle())
                .destination(plan.getDestination())
                .startDate(plan.getStartDate())
                .endDate(plan.getEndDate())
                .status(1)   // 计划中
                .createdAt(now)
                .updatedAt(now)
                .build();

        tripMapper.insert(trip);

        // 标记计划为已转换
        planMapper.markConverted(planUuid, trip.getUuid());

        // 将计划已填写的每日行程复制到新行程
        itineraryService.copyDaysFromPlanToTrip(planUuid, trip.getUuid());

        log.info("计划转行程: planUuid={} → tripUuid={}", planUuid, trip.getUuid());

        return TripVO.builder()
                .uuid(trip.getUuid())
                .title(trip.getTitle())
                .destination(trip.getDestination())
                .startDate(trip.getStartDate())
                .endDate(trip.getEndDate())
                .status(trip.getStatus())
                .createdAt(trip.getCreatedAt())
                .updatedAt(trip.getUpdatedAt())
                .build();
    }

    // ── 私有工具 ─────────────────────────────────────────────────────────────

    private Plan getPlanOrThrow(String uuid) {
        Plan plan = planMapper.getByUuid(uuid);
        if (plan == null) throw new BusinessException(ResultCode.PLAN_NOT_FOUND);
        return plan;
    }

    private void checkOwner(Plan plan, String userUuid) {
        if (!userUuid.equals(plan.getUserUuid())) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }
    }

    private PlanVO toVO(Plan p) {
        return PlanVO.builder()
                .uuid(p.getUuid())
                .title(p.getTitle())
                .destination(p.getDestination())
                .startDate(p.getStartDate())
                .endDate(p.getEndDate())
                .budget(p.getBudget())
                .budgetCurrency(p.getBudgetCurrency())
                .notes(p.getNotes())
                .convertedTripUuid(p.getConvertedTripUuid())
                .status(p.getStatus())
                .createdAt(p.getCreatedAt())
                .updatedAt(p.getUpdatedAt())
                .build();
    }
}
