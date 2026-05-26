package com.vago.travel.mapper;

import com.vago.travel.model.entity.ItinerarySpot;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface ItinerarySpotMapper {

    @Insert("""
            INSERT INTO itinerary_spots
              (uuid, day_uuid, name, address, category,
               sort_order, duration_minutes, notes, created_at, updated_at)
            VALUES
              (#{uuid}, #{dayUuid}, #{name}, #{address}, #{category},
               #{sortOrder}, #{durationMinutes}, #{notes}, #{createdAt}, #{updatedAt})
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(ItinerarySpot spot);

    /** 查询某天的全部景点（按 sortOrder 升序） */
    @Select("""
            SELECT * FROM itinerary_spots
            WHERE day_uuid = #{dayUuid}
            ORDER BY sort_order ASC, id ASC
            """)
    List<ItinerarySpot> listByDay(String dayUuid);

    /**
     * 一次性查询某归属实体下所有天的所有景点
     * 用于避免 N+1（Service 层再按 dayUuid 分组）
     */
    @Select("""
            SELECT s.* FROM itinerary_spots s
            INNER JOIN itinerary_days d ON s.day_uuid = d.uuid
            WHERE d.ref_uuid = #{refUuid} AND d.ref_type = #{refType}
            ORDER BY d.day_index ASC, s.sort_order ASC, s.id ASC
            """)
    List<ItinerarySpot> listByRef(@Param("refUuid") String refUuid,
                                   @Param("refType") int refType);

    @Select("SELECT * FROM itinerary_spots WHERE uuid = #{uuid}")
    ItinerarySpot getByUuid(String uuid);

    @Update("""
            UPDATE itinerary_spots SET
              name             = #{name},
              address          = #{address},
              category         = #{category},
              sort_order       = #{sortOrder},
              duration_minutes = #{durationMinutes},
              notes            = #{notes},
              updated_at       = NOW(3)
            WHERE uuid = #{uuid}
            """)
    int update(ItinerarySpot spot);

    /** 删除某天的所有景点（替换前清空） */
    @Delete("DELETE FROM itinerary_spots WHERE day_uuid = #{dayUuid}")
    int deleteByDay(String dayUuid);

    @Delete("DELETE FROM itinerary_spots WHERE uuid = #{uuid}")
    int deleteByUuid(String uuid);

    /**
     * 批量删除某归属实体的所有景点
     * （通过 JOIN itinerary_days 间接过滤）
     */
    @Delete("""
            DELETE s FROM itinerary_spots s
            INNER JOIN itinerary_days d ON s.day_uuid = d.uuid
            WHERE d.ref_uuid = #{refUuid} AND d.ref_type = #{refType}
            """)
    int deleteByRef(@Param("refUuid") String refUuid, @Param("refType") int refType);
}
