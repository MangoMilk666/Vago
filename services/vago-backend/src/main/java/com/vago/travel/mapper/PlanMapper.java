package com.vago.travel.mapper;

import com.vago.travel.model.entity.Plan;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface PlanMapper {

    @Insert("""
            INSERT INTO plans
              (uuid, user_uuid, title, destination, start_date, end_date,
               budget, budget_currency, notes, status, created_at, updated_at)
            VALUES
              (#{uuid}, #{userUuid}, #{title}, #{destination}, #{startDate}, #{endDate},
               #{budget}, #{budgetCurrency}, #{notes}, #{status}, #{createdAt}, #{updatedAt})
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(Plan plan);

    @Select("""
            SELECT * FROM plans
            WHERE user_uuid = #{userUuid} AND deleted_at IS NULL
            ORDER BY created_at DESC
            """)
    List<Plan> listByUserUuid(String userUuid);

    @Select("SELECT * FROM plans WHERE uuid = #{uuid} AND deleted_at IS NULL")
    Plan getByUuid(String uuid);

    @Update("""
            UPDATE plans SET
              title              = #{title},
              destination        = #{destination},
              start_date         = #{startDate},
              end_date           = #{endDate},
              budget             = #{budget},
              budget_currency    = #{budgetCurrency},
              notes              = #{notes},
              updated_at         = NOW(3)
            WHERE uuid = #{uuid}
            """)
    int update(Plan plan);

    /** 将计划标记为已转换并记录对应行程 UUID */
    @Update("""
            UPDATE plans SET
              status             = 1,
              converted_trip_uuid = #{tripUuid},
              updated_at         = NOW(3)
            WHERE uuid = #{planUuid}
            """)
    int markConverted(@Param("planUuid") String planUuid, @Param("tripUuid") String tripUuid);

    @Update("UPDATE plans SET deleted_at = NOW(3), updated_at = NOW(3) WHERE uuid = #{uuid}")
    int softDelete(String uuid);
}
