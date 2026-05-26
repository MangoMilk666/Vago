package com.vago.user.mapper;

import com.vago.user.model.entity.UserSettings;
import org.apache.ibatis.annotations.*;

@Mapper
public interface UserSettingsMapper {

    @Insert("INSERT INTO user_settings (user_id, gps_mode, fog_unlock_radius_m, default_visibility, " +
            "language, timezone, notification_checkin, updated_at) " +
            "VALUES (#{userId}, #{gpsMode}, #{fogUnlockRadiusM}, #{defaultVisibility}, " +
            "#{language}, #{timezone}, #{notificationCheckin}, #{updatedAt})")
    int insert(UserSettings settings);

    @Select("SELECT * FROM user_settings WHERE user_id = #{userId}")
    UserSettings getByUserId(Long userId);

    @Update("UPDATE user_settings SET gps_mode = #{gpsMode}, fog_unlock_radius_m = #{fogUnlockRadiusM}, " +
            "default_visibility = #{defaultVisibility}, language = #{language}, timezone = #{timezone}, " +
            "notification_checkin = #{notificationCheckin}, updated_at = NOW(3) WHERE user_id = #{userId}")
    int update(UserSettings settings);
}
