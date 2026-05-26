package com.vago.travel.mapper;

import com.vago.travel.model.entity.Trip;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface TripMapper {

    @Insert("""
            INSERT INTO trips
              (uuid, user_uuid, title, destination, cover_image_key,
               start_date, end_date, status, created_at, updated_at)
            VALUES
              (#{uuid}, #{userUuid}, #{title}, #{destination}, #{coverImageKey},
               #{startDate}, #{endDate}, #{status}, #{createdAt}, #{updatedAt})
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(Trip trip);

    /** 查询用户所有未删除行程，按创建时间倒序 */
    @Select("""
            SELECT * FROM trips
            WHERE user_uuid = #{userUuid} AND deleted_at IS NULL
            ORDER BY created_at DESC
            """)
    List<Trip> listByUserUuid(String userUuid);

    /** 查询历史行程（已完成） */
    @Select("""
            SELECT * FROM trips
            WHERE user_uuid = #{userUuid} AND status = 2 AND deleted_at IS NULL
            ORDER BY end_date DESC
            """)
    List<Trip> listHistoryByUserUuid(String userUuid);

    @Select("SELECT * FROM trips WHERE uuid = #{uuid} AND deleted_at IS NULL")
    Trip getByUuid(String uuid);

    @Update("""
            UPDATE trips SET
              title           = #{title},
              destination     = #{destination},
              cover_image_key = #{coverImageKey},
              start_date      = #{startDate},
              end_date        = #{endDate},
              status          = #{status},
              updated_at      = NOW(3)
            WHERE uuid = #{uuid}
            """)
    int update(Trip trip);

    @Update("UPDATE trips SET deleted_at = NOW(3), updated_at = NOW(3) WHERE uuid = #{uuid}")
    int softDelete(String uuid);
}
