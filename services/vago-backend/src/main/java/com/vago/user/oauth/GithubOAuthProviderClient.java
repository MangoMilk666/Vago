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
 * GitHub OAuth Client 实现类。
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
     * 获得第三方用户资料对象
     * @param authCode
     * @param redirectUri
     * @return
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
     * 从配置类写入GitHub OAuth配置变量
     * @param authCode
     * @param redirectUri
     * @param github
     * @return
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
        } catch (WebClientResponseException.BadRequest e) {
            log.warn("GitHub OAuth 换码失败: status={}, body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new BusinessException(ResultCode.OAUTH_CODE_INVALID);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("GitHub OAuth 换码异常: {}", e.getMessage(), e);
            throw new BusinessException(ResultCode.OAUTH_SERVICE_ERROR);
        }
    }

    /**
     * 获取GitHub用户信息
     * @param accessToken
     * @param github
     * @return
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
     * 获取GitHub邮箱？
     * @param userResponse
     * @param accessToken
     * @param github
     * @return
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
     * 返回已存在用户名或默认用户名
     * @param userResponse
     * @return
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
     * 返回过期的时间
     * @param expiresIn
     * @return
     */
    private LocalDateTime resolveExpiresAt(Long expiresIn) {
        return expiresIn == null ? null : LocalDateTime.now().plusSeconds(expiresIn);
    }

    /**
     * value是否为null / 只含所有空白符号
     * @param value
     * @return
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
