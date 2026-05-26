package com.vago.user.mapper;

import com.vago.user.model.entity.User;
import org.apache.ibatis.annotations.*;

@Mapper
public interface UserMapper {

    @Insert("INSERT INTO users (uuid, phone, email, nickname, avatar_oss_key, plan_type, article_quota, " +
            "ai_calls_today, status, created_at, updated_at) " +
            "VALUES (#{uuid}, #{phone}, #{email}, #{nickname}, #{avatarOssKey}, #{planType}, #{articleQuota}, " +
            "#{aiCallsToday}, #{status}, #{createdAt}, #{updatedAt})")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(User user);

    @Select("SELECT * FROM users WHERE id = #{id} AND deleted_at IS NULL")
    User getById(Long id);

    @Select("SELECT * FROM users WHERE uuid = #{uuid} AND deleted_at IS NULL")
    User getByUuid(String uuid);

    @Select("SELECT * FROM users WHERE phone = #{phone} AND deleted_at IS NULL")
    User getByPhone(String phone);

    @Select("SELECT * FROM users WHERE email = #{email} AND deleted_at IS NULL")
    User getByEmail(String email);

    @Update("UPDATE users SET nickname = #{nickname}, email = #{email}, avatar_oss_key = #{avatarOssKey}, " +
            "updated_at = #{updatedAt} WHERE id = #{id}")
    int update(User user);

    @Update("UPDATE users SET status = #{status}, updated_at = NOW(3) WHERE uuid = #{uuid}")
    int updateStatus(@Param("uuid") String uuid, @Param("status") Integer status);

    @Update("UPDATE users SET deleted_at = NOW(3), updated_at = NOW(3) WHERE uuid = #{uuid}")
    int softDelete(String uuid);
}
