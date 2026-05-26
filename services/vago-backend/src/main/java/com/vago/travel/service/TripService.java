package com.vago.travel.service;

import com.vago.travel.model.dto.TripCreateDTO;
import com.vago.travel.model.dto.TripUpdateDTO;
import com.vago.travel.model.vo.TripVO;

import java.util.List;

public interface TripService {

    /** 创建行程 */
    TripVO create(String userUuid, TripCreateDTO dto);

    /** 查询当前用户全部行程 */
    List<TripVO> listMyTrips(String userUuid);

    /** 查询历史（已完成）行程 */
    List<TripVO> listHistory(String userUuid);

    /** 查询行程详情 */
    TripVO getDetail(String userUuid, String tripUuid);

    /** 更新行程 */
    TripVO update(String userUuid, String tripUuid, TripUpdateDTO dto);

    /** 删除行程（软删除） */
    void delete(String userUuid, String tripUuid);
}
