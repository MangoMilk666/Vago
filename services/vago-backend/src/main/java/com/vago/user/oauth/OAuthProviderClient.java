package com.vago.user.oauth;

/**
 * OAuth provider 抽象，统一完成 authCode 换码与用户信息获取。
 *
 * <p>设计目标：
 * <ul>
 *   <li>Controller/Service 只依赖统一接口，不关心不同平台（GitHub/Google/微信等）的差异</li>
 *   <li>每个 provider 自己完成：authCode -> token -> 用户信息 拉取与字段标准化</li>
 * </ul>
 */
public interface OAuthProviderClient {

    /**
     * provider 标识（建议全小写），例如：github / google / wechat / apple。
     */
    String getProvider();

    /**
     * 将第三方回调的 authCode 换取用户资料。
     *
     * @param authCode     第三方回调授权码
     * @param redirectUri  发起授权时使用的 redirect_uri（部分平台要求严格一致）
     */
    OAuthUserProfile fetchUserProfile(String authCode, String redirectUri);
}
