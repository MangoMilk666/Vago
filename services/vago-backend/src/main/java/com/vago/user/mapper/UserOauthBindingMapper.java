package com.vago.user.mapper;

import com.vago.user.model.entity.UserOauthBinding;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface UserOauthBindingMapper {

    @Insert("INSERT INTO user_oauth_bindings (user_id, provider, open_id, access_token, expires_at, created_at, updated_at) " +
            "VALUES (#{userId}, #{provider}, #{openId}, #{accessToken}, #{expiresAt}, #{createdAt}, #{updatedAt})")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(UserOauthBinding binding);

    /**
     * 查询用户-第三方登录绑定
     */
    @Select("SELECT * FROM user_oauth_bindings WHERE provider = #{provider} AND open_id = #{openId}")
    UserOauthBinding getByProviderAndOpenId(@Param("provider") String provider,
                                            @Param("openId") String openId);

    @Select("SELECT provider FROM user_oauth_bindings WHERE user_id = #{userId}")
    List<String> getProvidersByUserId(Long userId);

    @Update("UPDATE user_oauth_bindings SET access_token = #{accessToken}, expires_at = #{expiresAt}, " +
            "updated_at = NOW(3) WHERE id = #{id}")
    int updateToken(UserOauthBinding binding);
}
