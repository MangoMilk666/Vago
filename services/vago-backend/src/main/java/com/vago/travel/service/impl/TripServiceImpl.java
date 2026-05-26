package com.vago.travel.service.impl;

import cn.hutool.core.util.IdUtil;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;
import com.vago.travel.mapper.TripMapper;
import com.vago.travel.model.dto.TripCreateDTO;
import com.vago.travel.model.dto.TripUpdateDTO;
import com.vago.travel.model.entity.Trip;
import com.vago.travel.model.vo.TripVO;
import com.vago.travel.service.TripService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
@Slf4j
public class TripServiceImpl implements TripService {

    @Autowired
    private TripMapper tripMapper;

    @Override
    public TripVO create(String userUuid, TripCreateDTO dto) {
        LocalDateTime now = LocalDateTime.now();
        Trip trip = Trip.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .userUuid(userUuid)
                .title(dto.getTitle())
                .destination(dto.getDestination())
                .coverImageKey(dto.getCoverImageKey())
                .startDate(dto.getStartDate())
                .endDate(dto.getEndDate())
                .status(1)   // 默认：计划中
                .createdAt(now)
                .updatedAt(now)
                .build();

        tripMapper.insert(trip);
        log.info("行程创建: uuid={}, userUuid={}", trip.getUuid(), userUuid);
        return toVO(trip);
    }

    @Override
    public List<TripVO> listMyTrips(String userUuid) {
        return tripMapper.listByUserUuid(userUuid)
                .stream().map(this::toVO).collect(Collectors.toList());
    }

    @Override
    public List<TripVO> listHistory(String userUuid) {
        return tripMapper.listHistoryByUserUuid(userUuid)
                .stream().map(this::toVO).collect(Collectors.toList());
    }

    @Override
    public TripVO getDetail(String userUuid, String tripUuid) {
        Trip trip = getTripOrThrow(tripUuid);
        checkOwner(trip, userUuid);
        return toVO(trip);
    }

    @Override
    public TripVO update(String userUuid, String tripUuid, TripUpdateDTO dto) {
        Trip trip = getTripOrThrow(tripUuid);
        checkOwner(trip, userUuid);

        // 按字段存在性局部更新
        if (dto.getTitle()          != null) trip.setTitle(dto.getTitle());
        if (dto.getDestination()    != null) trip.setDestination(dto.getDestination());
        if (dto.getCoverImageKey()  != null) trip.setCoverImageKey(dto.getCoverImageKey());
        if (dto.getStartDate()      != null) trip.setStartDate(dto.getStartDate());
        if (dto.getEndDate()        != null) trip.setEndDate(dto.getEndDate());
        if (dto.getStatus()         != null) trip.setStatus(dto.getStatus());

        tripMapper.update(trip);
        log.info("行程更新: uuid={}", tripUuid);
        // 重新查询确保数据最新
        return toVO(tripMapper.getByUuid(tripUuid));
    }

    @Override
    public void delete(String userUuid, String tripUuid) {
        Trip trip = getTripOrThrow(tripUuid);
        checkOwner(trip, userUuid);
        tripMapper.softDelete(tripUuid);
        log.info("行程删除: uuid={}", tripUuid);
    }

    // ── 私有工具 ─────────────────────────────────────────────────────────────

    private Trip getTripOrThrow(String uuid) {
        Trip trip = tripMapper.getByUuid(uuid);
        if (trip == null) throw new BusinessException(ResultCode.TRIP_NOT_FOUND);
        return trip;
    }

    private void checkOwner(Trip trip, String userUuid) {
        if (!userUuid.equals(trip.getUserUuid())) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }
    }

    private TripVO toVO(Trip t) {
        return TripVO.builder()
                .uuid(t.getUuid())
                .title(t.getTitle())
                .destination(t.getDestination())
                .coverImageKey(t.getCoverImageKey())
                .startDate(t.getStartDate())
                .endDate(t.getEndDate())
                .status(t.getStatus())
                .createdAt(t.getCreatedAt())
                .updatedAt(t.getUpdatedAt())
                .build();
    }
}
