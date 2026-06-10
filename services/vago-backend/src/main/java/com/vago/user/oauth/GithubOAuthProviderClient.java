package com.vago.user.oauth;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;
import com.vago.properties.OAuthProperties;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;

/**
 * GitHub OAuth provider 实现。
 *
 * <p>职责：将前端拿到的 authCode 换取 access_token，并拉取 GitHub 用户资料，统一映射为 {@link OAuthUserProfile}。
 * <p>说明：GitHub 的 user 接口常常不会直接返回 email（尤其是用户把邮箱设为私有），因此这里会额外请求 /user/emails。
 */
@Component
@Slf4j
public class GithubOAuthProviderClient implements OAuthProviderClient {

    private static final String PROVIDER = "github";
    private static final String USER_AGENT = "Vago-OAuth/1.0";

    @Autowired
    private WebClient.Builder webClientBuilder;

    @Autowired
    private OAuthProperties oauthProperties;

    @Override
    public String getProvider() {
        return PROVIDER;
    }

    /**
     * 将 GitHub authCode 兑换为统一的第三方用户资料。
     *
     * @param authCode     GitHub 回调携带的 code
     * @param redirectUri  本次授权使用的 redirect_uri（需与发起授权时一致）
     */
    @Override
    public OAuthUserProfile fetchUserProfile(String authCode, String redirectUri) {
        OAuthProperties.Github github = oauthProperties.getGithub();
        if (isBlank(github.getClientId()) || isBlank(github.getClientSecret())) {
            throw new BusinessException(ResultCode.OAUTH_SERVICE_ERROR.getCode(), "GitHub OAuth 未完成配置");
        }

        GithubTokenResponse tokenResponse = exchangeAccessToken(authCode, redirectUri, github);
        GithubUserResponse userResponse = fetchUser(tokenResponse.getAccessToken(), github);
        String email = resolveEmail(userResponse, tokenResponse.getAccessToken(), github);

        return OAuthUserProfile.builder()
                .provider(PROVIDER)
                .openId(String.valueOf(userResponse.getId()))
                .email(email)
                .nickname(resolveNickname(userResponse))
                .avatarUrl(userResponse.getAvatarUrl())
                .accessToken(tokenResponse.getAccessToken())
                .expiresAt(resolveExpiresAt(tokenResponse.getExpiresIn()))
                .build();
    }

    /**
     * GitHub：authCode → access_token。
     *
     * <p>注意：不要在日志中输出 access_token / response body，避免泄漏敏感信息。
     */
    private GithubTokenResponse exchangeAccessToken(String authCode, String redirectUri, OAuthProperties.Github github) {
        MultiValueMap<String, String> formData = new LinkedMultiValueMap<>();
        formData.add("client_id", github.getClientId());
        formData.add("client_secret", github.getClientSecret());
        formData.add("code", authCode);
        formData.add("redirect_uri", redirectUri);

        try {
            GithubTokenResponse response = webClientBuilder.build()
                    .post()
                    .uri(github.getTokenUrl())
                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                    .header(HttpHeaders.USER_AGENT, USER_AGENT)
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(BodyInserters.fromFormData(formData))
                    .retrieve()
                    .bodyToMono(GithubTokenResponse.class)
                    .block();

            if (response == null || isBlank(response.getAccessToken())) {
                throw new BusinessException(ResultCode.OAUTH_CODE_INVALID);
            }
            return response;
        } catch (WebClientResponseException e) {
            int status = e.getStatusCode().value();
            if (status == 400 || status == 401 || status == 403) {
                log.warn("GitHub OAuth 换码失败: status={}", status);
                throw new BusinessException(ResultCode.OAUTH_CODE_INVALID);
            }
            log.error("GitHub OAuth 换码异常: status={}", status, e);
            throw new BusinessException(ResultCode.OAUTH_SERVICE_ERROR);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("GitHub OAuth 换码异常: {}", e.getMessage(), e);
            throw new BusinessException(ResultCode.OAUTH_SERVICE_ERROR);
        }
    }

    /**
     * 获取 GitHub 用户信息（/user）。
     */
    private GithubUserResponse fetchUser(String accessToken, OAuthProperties.Github github) {
        try {
            GithubUserResponse response = webClientBuilder.build()
                    .get()
                    .uri(github.getUserUrl())
                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                    .header(HttpHeaders.USER_AGENT, USER_AGENT)
                    .headers(headers -> headers.setBearerAuth(accessToken))
                    .retrieve()
                    .bodyToMono(GithubUserResponse.class)
                    .block();

            if (response == null || response.getId() == null) {
                throw new BusinessException(ResultCode.OAUTH_SERVICE_ERROR.getCode(), "GitHub 用户信息为空");
            }
            return response;
        } catch (WebClientResponseException.Unauthorized e) {
            throw new BusinessException(ResultCode.OAUTH_CODE_INVALID);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("获取 GitHub 用户信息异常: {}", e.getMessage(), e);
            throw new BusinessException(ResultCode.OAUTH_SERVICE_ERROR);
        }
    }

    /**
     * 解析邮箱：优先用 /user 返回的 email；为空时再请求 /user/emails。
     */
    private String resolveEmail(GithubUserResponse userResponse, String accessToken, OAuthProperties.Github github) {
        if (!isBlank(userResponse.getEmail())) {
            return userResponse.getEmail();
        }

        try {
            List<GithubEmailResponse> emails = webClientBuilder.build()
                    .get()
                    .uri(github.getEmailsUrl())
                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                    .header(HttpHeaders.USER_AGENT, USER_AGENT)
                    .headers(headers -> headers.setBearerAuth(accessToken))
                    .retrieve()
                    .bodyToFlux(GithubEmailResponse.class)
                    .collectList()
                    .block();

            if (emails == null || emails.isEmpty()) {
                return null;
            }

            return emails.stream()
                    .filter(email -> Boolean.TRUE.equals(email.getVerified()))
                    .sorted(Comparator.comparing((GithubEmailResponse email) -> !Boolean.TRUE.equals(email.getPrimary())))
                    .map(GithubEmailResponse::getEmail)
                    .filter(email -> !isBlank(email))
                    .findFirst()
                    .orElse(null);
        } catch (Exception e) {
            log.warn("获取 GitHub 邮箱列表失败，继续使用无邮箱登录: {}", e.getMessage());
            return null;
        }
    }

    /**
     * 昵称策略：name > login > 默认昵称兜底。
     */
    private String resolveNickname(GithubUserResponse userResponse) {
        if (!isBlank(userResponse.getName())) {
            return userResponse.getName();
        }
        if (!isBlank(userResponse.getLogin())) {
            return userResponse.getLogin();
        }
        return "GitHub用户" + userResponse.getId();
    }

    /**
     * access_token 过期时间（GitHub 可能不返回 expires_in，此时为 null）。
     */
    private LocalDateTime resolveExpiresAt(Long expiresIn) {
        return expiresIn == null ? null : LocalDateTime.now().plusSeconds(expiresIn);
    }

    /**
     * 判空（null / 空串 / 全空白）。
     */
    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    @Data
    private static class GithubTokenResponse {
        @JsonProperty("access_token")
        private String accessToken;

        @JsonProperty("expires_in")
        private Long expiresIn;
    }

    @Data
    private static class GithubUserResponse {
        private Long id;
        private String login;
        private String name;
        private String email;

        @JsonProperty("avatar_url")
        private String avatarUrl;
    }

    @Data
    private static class GithubEmailResponse {
        private String email;
        private Boolean primary;
        private Boolean verified;
    }
}
