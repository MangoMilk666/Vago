package com.vago.user.oauth;

/**
 * OAuth provider 抽象，统一完成 authCode 换码与用户信息获取。
 */
public interface OAuthProviderClient {

    String getProvider();

    OAuthUserProfile fetchUserProfile(String authCode, String redirectUri);
}
