package com.vago.travel.mapper;

import com.vago.travel.model.entity.ItineraryDay;
import org.apache.ibatis.annotations.*;

import java.time.LocalDate;
import java.util.List;

@Mapper
public interface ItineraryDayMapper {

    @Insert("""
            INSERT INTO itinerary_days
              (uuid, ref_uuid, ref_type, day_date, day_index,
               transportation, accommodation,
               meal_breakfast, meal_lunch, meal_dinner,
               budget_day, notes, created_at, updated_at)
            VALUES
              (#{uuid}, #{refUuid}, #{refType}, #{dayDate}, #{dayIndex},
               #{transportation}, #{accommodation},
               #{mealBreakfast}, #{mealLunch}, #{mealDinner},
               #{budgetDay}, #{notes}, #{createdAt}, #{updatedAt})
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(ItineraryDay day);

    /** 按归属实体查全部天（按 dayIndex 升序）*/
    @Select("""
            SELECT * FROM itinerary_days
            WHERE ref_uuid = #{refUuid} AND ref_type = #{refType}
            ORDER BY day_index ASC
            """)
    List<ItineraryDay> listByRef(@Param("refUuid") String refUuid,
                                  @Param("refType") int refType);

    @Select("SELECT * FROM itinerary_days WHERE uuid = #{uuid}")
    ItineraryDay getByUuid(String uuid);

    /** 查询某归属在指定日期的 day 记录 */
    @Select("""
            SELECT * FROM itinerary_days
            WHERE ref_uuid = #{refUuid} AND ref_type = #{refType} AND day_date = #{dayDate}
            """)
    ItineraryDay getByRefAndDate(@Param("refUuid") String refUuid,
                                  @Param("refType") int refType,
                                  @Param("dayDate") LocalDate dayDate);

    /** 查询第 N 天 */
    @Select("""
            SELECT * FROM itinerary_days
            WHERE ref_uuid = #{refUuid} AND ref_type = #{refType} AND day_index = #{dayIndex}
            """)
    ItineraryDay getByRefAndIndex(@Param("refUuid") String refUuid,
                                   @Param("refType") int refType,
                                   @Param("dayIndex") int dayIndex);

    @Update("""
            UPDATE itinerary_days SET
              transportation  = #{transportation},
              accommodation   = #{accommodation},
              meal_breakfast  = #{mealBreakfast},
              meal_lunch      = #{mealLunch},
              meal_dinner     = #{mealDinner},
              budget_day      = #{budgetDay},
              notes           = #{notes},
              updated_at      = NOW(3)
            WHERE uuid = #{uuid}
            """)
    int update(ItineraryDay day);

    /** 将某归属的所有 day 批量复制到新归属（plan → trip 转换时使用）*/
    @Select("""
            SELECT * FROM itinerary_days
            WHERE ref_uuid = #{refUuid} AND ref_type = #{refType}
            ORDER BY day_index ASC
            """)
    List<ItineraryDay> listForCopy(@Param("refUuid") String refUuid,
                                    @Param("refType") int refType);

    /** 删除某归属的所有 day（配合 convertToTrip 清理旧数据） */
    @Delete("DELETE FROM itinerary_days WHERE ref_uuid = #{refUuid} AND ref_type = #{refType}")
    int deleteByRef(@Param("refUuid") String refUuid, @Param("refType") int refType);
}
