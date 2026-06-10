package com.vago.user.service.impl;

import cn.hutool.core.util.IdUtil;
import cn.hutool.crypto.digest.DigestUtil;
import com.vago.common.ResultCode;
import com.vago.constant.JwtClaimsConstant;
import com.vago.exception.BusinessException;
import com.vago.properties.JwtProperties;
import com.vago.user.mapper.UserMapper;
import com.vago.user.mapper.UserOauthBindingMapper;
import com.vago.user.mapper.UserSettingsMapper;
import com.vago.user.model.dto.*;
import com.vago.user.model.entity.User;
import com.vago.user.model.entity.UserOauthBinding;
import com.vago.user.model.entity.UserSettings;
import com.vago.user.model.vo.*;
import com.vago.user.oauth.OAuthProviderClient;
import com.vago.user.oauth.OAuthUserProfile;
import com.vago.user.service.UserService;
import com.vago.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 用户服务实现层
 *
 * <p>业务流程概览：
 * <pre>
 *   发送验证码  → validateSmsCode  → register / loginByPhone
 *   登录成功   → buildLoginVO（签发 AccessToken + RefreshToken，存 Redis）
 *   退出登录   → AccessToken 加入 Redis 黑名单，删除 RefreshToken
 *   刷新 Token → 校验 RefreshToken（Redis 比对），换发新 Token 对
 *   注销账号   → 验证码确认 → status=3，Redis 记录宽限截止时间
 *   撤销注销   → 检查 Redis 宽限期 → status=1
 * </pre>
 */
@Service
@Slf4j
public class UserServiceImpl implements UserService {

    // ── Redis Key 模板（与 JwtTokenUserInterceptor 中的黑名单 Key 保持一致）──────
    /** 短信验证码：vago:sms:code:{phone} */
    private static final String KEY_SMS_CODE    = "vago:sms:code:%s";
    /** 发送频率限制：vago:sms:limit:{phone} */
    private static final String KEY_SMS_LIMIT   = "vago:sms:limit:%s";
    /** Token 黑名单：vago:token:bl:{md5(token)} */
    private static final String KEY_TOKEN_BL    = "vago:token:bl:%s";
    /** Refresh Token 存储：vago:token:rt:{userUuid} */
    private static final String KEY_REFRESH_TOKEN = "vago:token:rt:%s";
    /** 注销宽限期截止时间：vago:cancel:{userUuid} */
    private static final String KEY_CANCEL      = "vago:cancel:%s";

    // ── 时效常量 ─────────────────────────────────────────────────────────────
    private static final long SMS_CODE_TTL_SEC  = 300L;   // 验证码有效期：5 分钟
    private static final long SMS_LIMIT_TTL_SEC = 60L;    // 发送冷却期：60 秒
    private static final long CANCEL_GRACE_SEC  = 7 * 24 * 3600L; // 注销宽限：7 天

    // ── 默认用户设置 ─────────────────────────────────────────────────────────
    private static final int DEFAULT_GPS_MODE           = 1;    // 标准精度
    private static final int DEFAULT_FOG_RADIUS_M       = 200;  // 200 米
    private static final int DEFAULT_VISIBILITY         = 0;    // 私密
    private static final String DEFAULT_LANGUAGE        = "zh-CN";
    private static final String DEFAULT_TIMEZONE        = "Asia/Shanghai";
    private static final int DEFAULT_NOTIFICATION       = 1;    // 开启
    private static final int DEFAULT_ARTICLE_QUOTA      = 10;
    private static final int DEFAULT_PLAN_TYPE          = 0;    // 免费版

    private static final DateTimeFormatter DT_FMT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final SecureRandom secureRandom = new SecureRandom();

    @Autowired private UserMapper userMapper;
    @Autowired private UserOauthBindingMapper oauthBindingMapper;
    @Autowired private UserSettingsMapper settingsMapper;
    @Autowired private JwtProperties jwtProperties;
    @Autowired private StringRedisTemplate redisTemplate;
    @Autowired private List<OAuthProviderClient> oauthProviderClients;

    // ══════════════════════════════════════════════════════════════════════════
    // 短信验证码
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    public void sendSmsCode(SmsSendDTO dto) {
        String phone = dto.getPhone();

        // 1. 频率限制：同一手机号 60 秒内只能发送一次
        String limitKey = String.format(KEY_SMS_LIMIT, phone);
        if (Boolean.TRUE.equals(redisTemplate.hasKey(limitKey))) {
            throw new BusinessException(ResultCode.SMS_RATE_LIMIT);
        }

        // 2. 生成 6 位随机验证码
        String code = String.format("%06d", secureRandom.nextInt(1_000_000));

        // 3. 存入 Redis（验证码 5 分钟有效，频率限制 60 秒）
        redisTemplate.opsForValue().set(
                String.format(KEY_SMS_CODE, phone), code, SMS_CODE_TTL_SEC, TimeUnit.SECONDS);
        redisTemplate.opsForValue().set(
                limitKey, "1", SMS_LIMIT_TTL_SEC, TimeUnit.SECONDS);

        // 4. 开发环境：直接 log 输出验证码，生产环境替换为真实短信 SDK 调用
        log.info("[DEV-ONLY] 手机号 {} 的验证码：{}", phone, code);
        // TODO: smsProvider.send(phone, code);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 注册
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginVO register(UserRegisterDTO dto) {
        String phone = dto.getPhone();

        // 1. 校验短信验证码
        validateAndConsumeSmsCode(phone, dto.getSmsCode());

        // 2. 手机号唯一性检查
        if (userMapper.getByPhone(phone) != null) {
            throw new BusinessException(ResultCode.PHONE_ALREADY_REGISTERED);
        }

        // 3. 创建用户
        LocalDateTime now = LocalDateTime.now();
        User user = User.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .phone(phone)
                .nickname(dto.getNickname())
                .planType(DEFAULT_PLAN_TYPE)
                .articleQuota(DEFAULT_ARTICLE_QUOTA)
                .aiCallsToday(0)
                .status(1)
                .createdAt(now)
                .updatedAt(now)
                .build();
        userMapper.insert(user);   // insert 后 user.id 由 @Options 回填

        // 4. 创建默认偏好设置
        createDefaultSettings(user.getId());

        log.info("新用户注册成功: uuid={}, phone={}", user.getUuid(), phone);
        return buildLoginVO(user, true);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 登录
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginVO loginByPhone(UserLoginPhoneDTO dto) {
        String phone = dto.getPhone();

        // 1. 校验短信验证码
        validateAndConsumeSmsCode(phone, dto.getSmsCode());

        // 2. 查询用户
        User user = userMapper.getByPhone(phone);

        // 3. 新手机号：自动注册（无需额外 /register 步骤）
        if (user == null) {
            LocalDateTime now = LocalDateTime.now();
            String defaultNickname = "旅行者" + phone.substring(phone.length() - 4);
            user = User.builder()
                    .uuid(IdUtil.fastSimpleUUID())
                    .phone(phone)
                    .nickname(defaultNickname)
                    .planType(DEFAULT_PLAN_TYPE)
                    .articleQuota(DEFAULT_ARTICLE_QUOTA)
                    .aiCallsToday(0)
                    .status(1)
                    .createdAt(now)
                    .updatedAt(now)
                    .build();
            userMapper.insert(user);
            createDefaultSettings(user.getId());
            log.info("手机号自动注册新用户: uuid={}, phone={}", user.getUuid(), phone);
            return buildLoginVO(user, true);
        }

        // 4. 校验账号状态，是否处于封禁/注销状态
        checkUserStatus(user);

        log.info("手机号登录成功: uuid={}", user.getUuid());
        return buildLoginVO(user, false);
    }

    /**
     * 第三方 OAuth 登录统一入口。
     *
     * <p>流程说明：
     * <pre>
     *   1) provider -> 选择对应 OAuthProviderClient
     *   2) authCode -> 换取第三方用户资料（openId/email/nickname/avatar）
     *   3) 优先用 (provider + openId) 查绑定表：
     *      - 存在：更新 token 信息 -> 登录
     *      - 不存在：尝试用 email 关联已有用户；否则创建新用户 -> 写绑定表 -> 登录
     * </pre>
     *
     * <p>注意：redirectUri 来自前端（用于换码），若要更严格防护可在服务端做白名单校验。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginVO loginByOAuth(UserLoginOAuthDTO dto) {
        String provider = normalizeProvider(dto.getProvider());
        OAuthProviderClient providerClient = getOAuthProviderClient(provider);
        OAuthUserProfile profile = providerClient.fetchUserProfile(dto.getAuthCode(), dto.getRedirectUri());

        UserOauthBinding binding = oauthBindingMapper.getByProviderAndOpenId(provider, profile.getOpenId());
        // 已绑定：直接登录（并同步第三方侧的 token/资料）
        if (binding != null) {
            updateOauthBindingToken(binding, profile);
            User user = userMapper.getById(binding.getUserId());
            if (user == null) {
                throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND);
            }
            checkUserStatus(user);
            syncUserProfileFromOAuth(user, profile);
            log.info("OAuth 登录成功: provider={}, uuid={}", provider, user.getUuid());
            return buildLoginVO(user, false);
        }

        // 未绑定：尝试用邮箱关联老用户（避免同一邮箱多账号），否则创建新用户
        User user = findUserByOAuthEmail(profile);
        boolean isNewUser = false;
        if (user == null) {
            user = createUserForOAuth(profile);
            isNewUser = true;
        } else {
            checkUserStatus(user);
            syncUserProfileFromOAuth(user, profile);
        }
        bindOAuthAccount(user, profile);
        log.info("OAuth 登录并绑定成功: provider={}, uuid={}", provider, user.getUuid());
        return buildLoginVO(user, isNewUser);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // Token 管理
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    public TokenVO refreshToken(TokenRefreshDTO dto) {
        String oldRefreshToken = dto.getRefreshToken();

        // 1. 解析 JWT（过期或签名非法时直接 401）
        Claims claims;
        try {
            claims = JwtUtil.parseJWT(jwtProperties.getSecretKey(), oldRefreshToken);
        } catch (Exception e) {
            throw new BusinessException(ResultCode.TOKEN_INVALID);
        }

        String userUuid = claims.get(JwtClaimsConstant.USER_UUID, String.class);

        // 2. 校验 Redis 中存储的 RefreshToken 是否与客户端一致（防止重放）
        String rtKey = String.format(KEY_REFRESH_TOKEN, userUuid);
        String storedToken = redisTemplate.opsForValue().get(rtKey);
        if (!oldRefreshToken.equals(storedToken)) {
            throw new BusinessException(ResultCode.TOKEN_INVALID);
        }

        // 3. 查询用户并校验状态
        User user = userMapper.getByUuid(userUuid);
        if (user == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND);
        }
        checkUserStatus(user);

        // 4. 签发新 Token 对（旧 RefreshToken 被覆盖，自动失效）
        Map<String, Object> newClaims = buildClaims(user);
        String newAccessToken  = JwtUtil.createJWT(jwtProperties.getSecretKey(),
                jwtProperties.getAccessTokenTtl(), newClaims);
        String newRefreshToken = JwtUtil.createJWT(jwtProperties.getSecretKey(),
                jwtProperties.getRefreshTokenTtl(), newClaims);

        redisTemplate.opsForValue().set(rtKey, newRefreshToken,
                jwtProperties.getRefreshTokenTtl(), TimeUnit.MILLISECONDS);

        log.info("Token 刷新成功: uuid={}", userUuid);
        return TokenVO.builder()
                .accessToken(newAccessToken)
                .refreshToken(newRefreshToken)
                .expiresIn(jwtProperties.getAccessTokenTtl() / 1000)
                .build();
    }

    @Override
    public void logout(String accessToken) {
        if (accessToken == null || accessToken.isBlank()) {
            return;
        }
        try {
            Claims claims = JwtUtil.parseJWT(jwtProperties.getSecretKey(), accessToken);

            // 将 AccessToken 加入黑名单，剩余有效期内不可再用
            long remainingMs = claims.getExpiration().getTime() - System.currentTimeMillis();
            if (remainingMs > 0) {
                String blKey = String.format(KEY_TOKEN_BL, DigestUtil.md5Hex(accessToken));
                redisTemplate.opsForValue().set(blKey, "1", remainingMs, TimeUnit.MILLISECONDS);
            }

            // 同步删除 RefreshToken，使 Token 对完全失效
            String userUuid = claims.get(JwtClaimsConstant.USER_UUID, String.class);
            redisTemplate.delete(String.format(KEY_REFRESH_TOKEN, userUuid));

            log.info("用户退出登录: uuid={}", userUuid);
        } catch (Exception e) {
            // Token 已过期或非法时忽略，退出仍视为成功
            log.warn("logout 时 Token 解析失败（已忽略）: {}", e.getMessage());
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 用户信息
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    public UserVO getProfile(String userUuid) {
        User user = getUserOrThrow(userUuid);
        List<String> providers = oauthBindingMapper.getProvidersByUserId(user.getId());
        return toUserVO(user, providers);
    }

    @Override
    public UserVO updateProfile(String userUuid, UserUpdateProfileDTO dto) {
        User user = getUserOrThrow(userUuid);

        // 邮箱唯一性检查（排除自身）
        if (dto.getEmail() != null && !dto.getEmail().isBlank()) {
            User emailOwner = userMapper.getByEmail(dto.getEmail());
            if (emailOwner != null && !emailOwner.getUuid().equals(userUuid)) {
                throw new BusinessException(ResultCode.EMAIL_ALREADY_USED);
            }
            user.setEmail(dto.getEmail());
        }

        if (dto.getNickname() != null && !dto.getNickname().isBlank()) {
            user.setNickname(dto.getNickname());
        }
        if (dto.getAvatarUuid() != null && !dto.getAvatarUuid().isBlank()) {
            user.setAvatarOssKey(dto.getAvatarUuid());
        }

        user.setUpdatedAt(LocalDateTime.now());
        userMapper.update(user);

        log.info("用户信息更新: uuid={}", userUuid);
        List<String> providers = oauthBindingMapper.getProvidersByUserId(user.getId());
        return toUserVO(user, providers);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 用户设置
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    public UserSettingsVO getSettings(String userUuid) {
        User user = getUserOrThrow(userUuid);
        UserSettings settings = settingsMapper.getByUserId(user.getId());
        if (settings == null) {
            settings = createDefaultSettings(user.getId());
        }
        return toSettingsVO(settings);
    }

    @Override
    public UserSettingsVO updateSettings(String userUuid, UserUpdateSettingsDTO dto) {
        User user = getUserOrThrow(userUuid);
        UserSettings settings = settingsMapper.getByUserId(user.getId());
        if (settings == null) {
            settings = createDefaultSettings(user.getId());
        }

        // 按字段存在性做局部更新（null 字段不覆盖）
        if (dto.getGpsMode()            != null) settings.setGpsMode(dto.getGpsMode());
        if (dto.getFogUnlockRadiusM()   != null) settings.setFogUnlockRadiusM(dto.getFogUnlockRadiusM());
        if (dto.getDefaultVisibility()  != null) settings.setDefaultVisibility(dto.getDefaultVisibility());
        if (dto.getLanguage()           != null) settings.setLanguage(dto.getLanguage());
        if (dto.getTimezone()           != null) settings.setTimezone(dto.getTimezone());
        if (dto.getNotificationCheckin() != null) {
            settings.setNotificationCheckin(Boolean.TRUE.equals(dto.getNotificationCheckin()) ? 1 : 0);
        }

        settingsMapper.update(settings);
        log.info("用户设置更新: uuid={}", userUuid);
        return toSettingsVO(settings);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 账号注销
    // ══════════════════════════════════════════════════════════════════════════

    @Override
    public String cancelAccount(String userUuid, AccountCancelDTO dto) {
        User user = getUserOrThrow(userUuid);

        // 校验账号当前状态
        if (user.getStatus() == 3) {
            throw new BusinessException(ResultCode.ACCOUNT_ALREADY_CANCELLING);
        }

        // 用账号绑定的手机号校验验证码
        validateAndConsumeSmsCode(user.getPhone(), dto.getSmsCode());

        // 更新状态为注销中
        userMapper.updateStatus(userUuid, 3);

        // 在 Redis 记录宽限截止时间（7 天后自动过期 = 宽限期结束）
        LocalDateTime deadline = LocalDateTime.now().plusDays(7);
        redisTemplate.opsForValue().set(
                String.format(KEY_CANCEL, userUuid),
                deadline.format(DT_FMT),
                CANCEL_GRACE_SEC, TimeUnit.SECONDS);

        log.info("用户申请注销: uuid={}, deadline={}", userUuid, deadline);
        return deadline.format(DT_FMT);
    }

    @Override
    public void revokeCancelAccount(String userUuid) {
        User user = getUserOrThrow(userUuid);

        // 必须处于注销中状态
        if (user.getStatus() != 3) {
            throw new BusinessException(ResultCode.ACCOUNT_NOT_CANCELLING);
        }

        // 校验宽限期是否已过（Redis key 过期即代表宽限期结束）
        String cancelKey = String.format(KEY_CANCEL, userUuid);
        if (!Boolean.TRUE.equals(redisTemplate.hasKey(cancelKey))) {
            throw new BusinessException(ResultCode.CANCEL_REVOKE_EXPIRED);
        }

        // 恢复正常状态，删除注销记录
        userMapper.updateStatus(userUuid, 1);
        redisTemplate.delete(cancelKey);

        log.info("用户撤销注销: uuid={}", userUuid);
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 私有工具方法
    // ══════════════════════════════════════════════════════════════════════════

    /**
     * 校验短信验证码并消费（一次性，验证后立即从 Redis 删除）
     */
    private void validateAndConsumeSmsCode(String phone, String inputCode) {
        String codeKey = String.format(KEY_SMS_CODE, phone);
        String storedCode = redisTemplate.opsForValue().get(codeKey);
        if (storedCode == null || !storedCode.equals(inputCode)) {
            throw new BusinessException(ResultCode.SMS_CODE_INVALID);
        }
        // 验证成功后立即删除，防止重复使用
        redisTemplate.delete(codeKey);
    }

    /**
     * 校验账号状态，封禁或注销中时抛出业务异常
     */
    private void checkUserStatus(User user) {
        if (user.getStatus() == 2) throw new BusinessException(ResultCode.ACCOUNT_BANNED);
        if (user.getStatus() == 3) throw new BusinessException(ResultCode.ACCOUNT_CANCELLING);
    }

    /**
     * 按 UUID 查询用户，不存在时抛出业务异常
     */
    private User getUserOrThrow(String userUuid) {
        User user = userMapper.getByUuid(userUuid);
        if (user == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND);
        }
        return user;
    }

    /**
     * 根据 provider 选择对应的 OAuthProviderClient 实现。
     *
     * <p>通过 Spring 注入的 oauthProviderClients 列表动态匹配，便于后续扩展 Google/微信等。
     */
    private OAuthProviderClient getOAuthProviderClient(String provider) {
        return oauthProviderClients.stream()
                .filter(client -> client.getProvider().equalsIgnoreCase(provider))
                .findFirst()
                .orElseThrow(() -> new BusinessException(
                        ResultCode.PARAM_INVALID.getCode(),
                        "暂不支持的 OAuth provider: " + provider));
    }

    /**
     * 规范 provider：去空格 + 转小写。
     */
    private String normalizeProvider(String provider) {
        return provider == null ? null : provider.trim().toLowerCase(Locale.ROOT);
    }

    /**
     * 使用第三方邮箱查找已有用户（若第三方不返回邮箱则返回 null）。
     *
     * <p>目的：当用户用同一邮箱在不同 provider 登录时，尽量合并为一个用户账号。
     */
    private User findUserByOAuthEmail(OAuthUserProfile profile) {
        if (profile.getEmail() != null && !profile.getEmail().isBlank()) {
            return userMapper.getByEmail(profile.getEmail());
        }
        return null;
    }

    /**
     * 创建新用户并入库（OAuth 首次登录且无法匹配到旧用户时）。
     *
     * <p>说明：当前把第三方 avatarUrl 暂存在 avatarOssKey 字段中，后续如接入 OSS/CDN 可再做转换。
     */
    private User createUserForOAuth(OAuthUserProfile profile) {
        LocalDateTime now = LocalDateTime.now();
        User user = User.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .email(profile.getEmail())
                .nickname(defaultNickname(profile))
                .avatarOssKey(profile.getAvatarUrl())
                .planType(DEFAULT_PLAN_TYPE)
                .articleQuota(DEFAULT_ARTICLE_QUOTA)
                .aiCallsToday(0)
                .status(1)
                .createdAt(now)
                .updatedAt(now)
                .build();
        userMapper.insert(user);
        createDefaultSettings(user.getId());
        return user;
    }

    /**
     * 创建用户与第三方账号绑定关系（user_oauth_bindings）。
     *
     * <p>绑定主键为 (provider, openId)，用于后续同平台免注册直接登录。
     */
    private void bindOAuthAccount(User user, OAuthUserProfile profile) {
        LocalDateTime now = LocalDateTime.now();
        UserOauthBinding binding = UserOauthBinding.builder()
                .userId(user.getId())
                .provider(profile.getProvider())
                .openId(profile.getOpenId())
                .accessToken(profile.getAccessToken())
                .expiresAt(profile.getExpiresAt())
                .createdAt(now)
                .updatedAt(now)
                .build();
        oauthBindingMapper.insert(binding);
    }

    /**
     * 更新绑定记录的 token 信息。
     *
     * <p>注意：当前为直存 accessToken；如有更高安全要求，建议加密存储或仅存短期 token/不落库。
     */
    private void updateOauthBindingToken(UserOauthBinding binding, OAuthUserProfile profile) {
        binding.setAccessToken(profile.getAccessToken());
        binding.setExpiresAt(profile.getExpiresAt());
        oauthBindingMapper.updateToken(binding);
    }

    /**
     * 从第三方资料补齐用户信息（只在本地字段为空时才写入，避免覆盖用户手动修改的资料）。
     */
    private void syncUserProfileFromOAuth(User user, OAuthUserProfile profile) {
        boolean updated = false;

        if ((user.getNickname() == null || user.getNickname().isBlank())
                && profile.getNickname() != null && !profile.getNickname().isBlank()) {
            user.setNickname(profile.getNickname());
            updated = true;
        }

        if ((user.getAvatarOssKey() == null || user.getAvatarOssKey().isBlank())
                && profile.getAvatarUrl() != null && !profile.getAvatarUrl().isBlank()) {
            user.setAvatarOssKey(profile.getAvatarUrl());
            updated = true;
        }

        if ((user.getEmail() == null || user.getEmail().isBlank())
                && profile.getEmail() != null && !profile.getEmail().isBlank()) {
            User emailOwner = userMapper.getByEmail(profile.getEmail());
            if (emailOwner == null || emailOwner.getId().equals(user.getId())) {
                user.setEmail(profile.getEmail());
                updated = true;
            }
        }

        if (updated) {
            user.setUpdatedAt(LocalDateTime.now());
            userMapper.update(user);
        }
    }

    /**
     * 返回已存在或默认用户名
     * @param profile
     * @return
     */
    private String defaultNickname(OAuthUserProfile profile) {
        if (profile.getNickname() != null && !profile.getNickname().isBlank()) {
            return profile.getNickname();
        }
        String suffix = profile.getOpenId() == null ? IdUtil.fastSimpleUUID().substring(0, 6)
                : profile.getOpenId().substring(Math.max(0, profile.getOpenId().length() - 6));
        return "旅行者" + suffix;
    }

    /**
     * 签发 Token 对，存储 RefreshToken 到 Redis，构造 LoginVO 返回
     */
    private LoginVO buildLoginVO(User user, boolean isNewUser) {
        Map<String, Object> claims = buildClaims(user);

        String accessToken  = JwtUtil.createJWT(jwtProperties.getSecretKey(),
                jwtProperties.getAccessTokenTtl(), claims);
        String refreshToken = JwtUtil.createJWT(jwtProperties.getSecretKey(),
                jwtProperties.getRefreshTokenTtl(), claims);

        // RefreshToken 持久化到 Redis（覆盖式写入，旧 Token 自动失效）
        redisTemplate.opsForValue().set(
                String.format(KEY_REFRESH_TOKEN, user.getUuid()),
                refreshToken,
                jwtProperties.getRefreshTokenTtl(), TimeUnit.MILLISECONDS);

        List<String> providers = oauthBindingMapper.getProvidersByUserId(user.getId());

        return LoginVO.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .expiresIn(jwtProperties.getAccessTokenTtl() / 1000)
                .isNewUser(isNewUser)
                .userInfo(toUserVO(user, providers))
                .build();
    }

    /**
     * 构造 JWT Payload（userUuid + userId）
     */
    private Map<String, Object> buildClaims(User user) {
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.USER_UUID, user.getUuid());
        claims.put(JwtClaimsConstant.USER_ID, user.getId());
        return claims;
    }

    /**
     * User 实体 → UserVO（手机号中间 4 位脱敏）
     */
    private UserVO toUserVO(User user, List<String> providers) {
        return UserVO.builder()
                .uuid(user.getUuid())
                .nickname(user.getNickname())
                .phone(maskPhone(user.getPhone()))
                .email(user.getEmail())
                .avatarUrl(user.getAvatarOssKey()) // TODO: OSS key → CDN URL 转换
                .planType(user.getPlanType())
                .articleQuota(user.getArticleQuota())
                .status(user.getStatus())
                .createdAt(user.getCreatedAt())
                .oauthProviders(providers != null ? providers : List.of())
                .build();
    }

    /**
     * UserSettings 实体 → UserSettingsVO
     */
    private UserSettingsVO toSettingsVO(UserSettings s) {
        return UserSettingsVO.builder()
                .gpsMode(s.getGpsMode())
                .fogUnlockRadiusM(s.getFogUnlockRadiusM())
                .defaultVisibility(s.getDefaultVisibility())
                .language(s.getLanguage())
                .timezone(s.getTimezone())
                .notificationCheckin(
                        s.getNotificationCheckin() != null && s.getNotificationCheckin() == 1)
                .build();
    }

    /**
     * 手机号脱敏：138****1000
     */
    private String maskPhone(String phone) {
        if (phone == null || phone.length() < 7) return phone;
        return phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
    }

    /**
     * 插入一条默认用户设置记录
     */
    private UserSettings createDefaultSettings(Long userId) {
        UserSettings settings = UserSettings.builder()
                .userId(userId)
                .gpsMode(DEFAULT_GPS_MODE)
                .fogUnlockRadiusM(DEFAULT_FOG_RADIUS_M)
                .defaultVisibility(DEFAULT_VISIBILITY)
                .language(DEFAULT_LANGUAGE)
                .timezone(DEFAULT_TIMEZONE)
                .notificationCheckin(DEFAULT_NOTIFICATION)
                .updatedAt(LocalDateTime.now())
                .build();
        settingsMapper.insert(settings);
        return settings;
    }
}
