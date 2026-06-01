package com.vago.travel.service.impl;

import cn.hutool.core.util.IdUtil;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.vago.ai.service.AiService;
import com.vago.common.PageVO;
import com.vago.common.ResultCode;
import com.vago.exception.BusinessException;
import com.vago.travel.mapper.GuideMapper;
import com.vago.travel.model.dto.GuideCreateDTO;
import com.vago.travel.model.dto.GuideUpdateDTO;
import com.vago.travel.model.entity.Guide;
import com.vago.travel.model.vo.GuideVO;
import com.vago.travel.service.GuideService;
import com.vago.user.mapper.UserMapper;
import com.vago.user.model.entity.User;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

@Service
@Slf4j
public class GuideServiceImpl implements GuideService {

    // AI 向量化状态：0=PENDING，与 AiServiceImpl 中的常量保持一致
    private static final int AI_STATUS_PENDING = 0;

    // Redis key 前缀
    // 点赞计数 key：vago:guide:like:count:{uuid}  →  String（INCR）
    static final String LIKE_COUNT_KEY_PREFIX = "vago:guide:like:count:";
    // 已点赞用户集合 key：vago:guide:like:users:{uuid}  →  Set<userUuid>（SADD 防重）
    static final String LIKE_USERS_KEY_PREFIX = "vago:guide:like:users:";
    // 浏览量前缀（预留，暂未使用 Redis 缓存）
    private static final String GUIDE_VIEW_KEY_PREFIX = "vago:guide:view:";

    @Autowired
    private GuideMapper guideMapper;

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private AiService aiService;

    // 本质上就是 RedisTemplate<String, String>
    // key 和 value 都用 StringRedisSerializer，Redis 里存的是可读字符串
    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    /** Jackson ObjectMapper：用于 imageKeys / tags 的 JSON 序列化 */
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public PageVO<GuideVO> listPublished(int page, int size) {
        int offset = (page - 1) * size;
        List<Guide> guides = guideMapper.listPublished(size, offset);
        long total = guideMapper.countPublished();

        List<GuideVO> records = guides.stream()
                .map(g -> toVO(g, fetchAuthor(g.getUserUuid())))
                .collect(Collectors.toList());

        return PageVO.<GuideVO>builder()
                .total(total)
                .page(page)
                .size(size)
                .records(records)
                .build();
    }

    @Override
    public List<GuideVO> listMine(String userUuid) {
        User author = userMapper.getByUuid(userUuid);
        return guideMapper.listByUserUuid(userUuid)
                .stream().map(g -> toVO(g, author)).collect(Collectors.toList());
    }

    @Override
    public GuideVO getDetail(String userUuid, String guideUuid) {
        Guide guide = getGuideOrThrow(guideUuid);

        // 浏览量 +1（非作者时才计）
        if (!guide.getUserUuid().equals(userUuid)) {
            guideMapper.incrementViewCount(guideUuid);
            guide.setViewCount(guide.getViewCount() == null ? 1 : guide.getViewCount() + 1);
        }

        // 从 Redis 读取实时点赞数（比 DB 更新，因为 flush 是异步的）
        String countStr = stringRedisTemplate.opsForValue().get(LIKE_COUNT_KEY_PREFIX + guideUuid);
        if (countStr != null) {
            try {
                guide.setLikeCount(Integer.parseInt(countStr));
            } catch (NumberFormatException e) {
                log.warn("like count parse error: key={} val={}", guideUuid, countStr);
            }
        }

        // 检查当前用户是否已点赞
        Boolean liked = stringRedisTemplate.opsForSet()
                .isMember(LIKE_USERS_KEY_PREFIX + guideUuid, userUuid);

        return toVO(guide, fetchAuthor(guide.getUserUuid()), liked);
    }

    /**
     * 新增攻略。
     * 若直接发布（status=1），立即将 aiStatus 置为 PENDING 并异步触发向量化。
     * 草稿（status=0）不进行向量化，aiStatus 保持 null。
     */
    @Override
    public GuideVO create(String userUuid, GuideCreateDTO dto) {
        LocalDateTime now = LocalDateTime.now();
        int guideStatus = dto.getStatus() != null ? dto.getStatus() : 1;
        // 已发布则设 PENDING，如果是草稿不写入索引
        Integer aiStatus = (guideStatus == 1) ? AI_STATUS_PENDING : null;

        Guide guide = Guide.builder()
                .uuid(IdUtil.fastSimpleUUID())
                .userUuid(userUuid)
                .title(dto.getTitle())
                .destination(dto.getDestination())
                .coverImageKey(dto.getCoverImageKey())
                .imageKeys(toJson(dto.getImageKeys()))
                .content(dto.getContent())
                .tags(toJson(dto.getTags()))
                .viewCount(0)
                .likeCount(0)
                .status(guideStatus)
                .aiStatus(aiStatus)
                .createdAt(now)
                .updatedAt(now)
                .build();

        guideMapper.insert(guide);
        log.info("攻略创建: uuid={} userUuid={} status={}", guide.getUuid(), userUuid, guideStatus);

        // 已发布则异步触发向量化（fire-and-forget）
        if (guideStatus == 1) {
            aiService.indexGuideAsync(guide);
        }

        return toVO(guide, fetchAuthor(userUuid));
    }

    /**
     * 更新攻略。
     * 更新后仍为已发布状态 → 重新向量化（幂等 upsert）；
     * 从已发布降为草稿 → 删除向量数据并清空 aiStatus。
     */
    @Override
    public GuideVO update(String userUuid, String guideUuid, GuideUpdateDTO dto) {
        Guide guide = getGuideOrThrow(guideUuid);
        checkOwner(guide, userUuid);

        // 复制dto中的成员变量
        if (dto.getTitle()          != null) guide.setTitle(dto.getTitle());
        if (dto.getDestination()    != null) guide.setDestination(dto.getDestination());
        if (dto.getCoverImageKey()  != null) guide.setCoverImageKey(dto.getCoverImageKey());
        if (dto.getImageKeys()      != null) guide.setImageKeys(toJson(dto.getImageKeys()));
        if (dto.getContent()        != null) guide.setContent(dto.getContent());
        if (dto.getTags()           != null) guide.setTags(toJson(dto.getTags()));
        if (dto.getStatus()         != null) guide.setStatus(dto.getStatus());

        guideMapper.update(guide);
        log.info("攻略更新: uuid={} newStatus={}", guideUuid, guide.getStatus());

        Guide updated = guideMapper.getByUuid(guideUuid);

        if (updated.getStatus() == 1) {
            // 更新后仍为已发布 → 重置为 PENDING 并异步重新向量化
            guideMapper.updateAiStatus(guideUuid, AI_STATUS_PENDING);
            updated.setAiStatus(AI_STATUS_PENDING);
            aiService.indexGuideAsync(updated);
        } else {
            // 降为草稿 → 清空向量数据
            guideMapper.updateAiStatus(guideUuid, null);
            updated.setAiStatus(null);
            aiService.deleteGuideAsync(guideUuid, userUuid);
        }

        return toVO(updated, fetchAuthor(userUuid));
    }

    /**
     * 删除攻略。
     * 软删除后异步通知 vago-ai 清理对应向量数据。
     */
    @Override
    public void delete(String userUuid, String guideUuid) {
        Guide guide = getGuideOrThrow(guideUuid);
        checkOwner(guide, userUuid);
        guideMapper.softDelete(guideUuid);
        log.info("攻略删除: uuid={}", guideUuid);

        // 若曾经发布过，异步清理向量库（草稿从未索引，deleteGuideAsync 内部忽略处理）
        if (guide.getAiStatus() != null) {
            aiService.deleteGuideAsync(guideUuid, userUuid);
        }
    }

    /**
     * 点赞流程：
     * 1. 验证攻略存在
     * 2. SADD userUuid 到 like:users set，返回 0 说明已点赞，直接返回
     * 3. SETNX 初始化 like:count（避免 Redis 冷启动时计数从 0 开始）
     * 4. INCR like:count（原子操作）
     * DB 写入由 LikeFlushJob 异步批量完成，不在此处同步写入。
     */
    @Override
    public void like(String userUuid, String guideUuid) {
        Guide guide = getGuideOrThrow(guideUuid);

        String usersKey = LIKE_USERS_KEY_PREFIX + guideUuid;
        String countKey = LIKE_COUNT_KEY_PREFIX + guideUuid;

        // SADD 返回 0 = 已经点赞过，幂等退出
        Long added = stringRedisTemplate.opsForSet().add(usersKey, userUuid);
        if (added == null || added == 0) {
            log.debug("忽略重复点赞: userUuid={} guideUuid={}", userUuid, guideUuid);
            return;
        }

        // count key 不存在时，从 DB 初始化（SETNX 保证并发安全）
        int dbCount = guide.getLikeCount() != null ? guide.getLikeCount() : 0;
        stringRedisTemplate.opsForValue().setIfAbsent(countKey, String.valueOf(dbCount));

        // 原子自增
        stringRedisTemplate.opsForValue().increment(countKey);
        log.debug("点赞记录在Redis: userUuid={} guideUuid={}", userUuid, guideUuid);
    }

    /**
     * 手动触发向量化：将攻略重新加入（或首次加入）AI 知识库。
     *
     * <p>适用于旧数据补索引（aiStatus=null）和索引失败重试（aiStatus=3）。
     * 草稿不可索引，调用时抛出 PARAM_INVALID。
     */
    @Override
    public GuideVO triggerIndex(String userUuid, String guideUuid) {
        Guide guide = getGuideOrThrow(guideUuid);
        checkOwner(guide, userUuid);

        if (guide.getStatus() != 1) {
            throw new BusinessException(ResultCode.PARAM_INVALID);
        }

        // 重置为 PENDING，异步触发向量化
        guideMapper.updateAiStatus(guideUuid, AI_STATUS_PENDING);
        guide.setAiStatus(AI_STATUS_PENDING);
        aiService.indexGuideAsync(guide);

        log.info("手动触发向量化: uuid={} userUuid={}", guideUuid, userUuid);
        Guide updated = guideMapper.getByUuid(guideUuid);
        return toVO(updated, fetchAuthor(userUuid));
    }

    // ── 私有工具 ─────────────────────────────────────────────────────────────

    /**
     * 验证帖子是否存在
     */
    private Guide getGuideOrThrow(String uuid) {
        Guide guide = guideMapper.getByUuid(uuid);
        if (guide == null) throw new BusinessException(ResultCode.GUIDE_NOT_FOUND);
        return guide;
    }

    /**
     * 判断当前用户是否是帖子发布者
     */
    private void checkOwner(Guide guide, String userUuid) {
        if (!userUuid.equals(guide.getUserUuid())) {
            throw new BusinessException(ResultCode.FORBIDDEN);
        }
    }

    private User fetchAuthor(String userUuid) {
        return userMapper.getByUuid(userUuid);
    }

    /** Guide 实体 → GuideVO（含作者信息，liked 为 null 时不填充） */
    private GuideVO toVO(Guide g, User author) {
        return toVO(g, author, null);
    }

    /** Guide 实体 → GuideVO（含作者信息 + 当前用户点赞状态） */
    private GuideVO toVO(Guide g, User author, Boolean liked) {
        GuideVO.GuideVOBuilder builder = GuideVO.builder()
                .uuid(g.getUuid())
                .title(g.getTitle())
                .destination(g.getDestination())
                .coverImageKey(g.getCoverImageKey())
                .imageKeys(fromJson(g.getImageKeys()))
                .content(g.getContent())
                .tags(fromJson(g.getTags()))
                .viewCount(g.getViewCount())
                .likeCount(g.getLikeCount())
                .liked(liked)
                .status(g.getStatus())
                .aiStatus(g.getAiStatus())
                .createdAt(g.getCreatedAt())
                .updatedAt(g.getUpdatedAt());

        if (author != null) {
            builder.authorUuid(author.getUuid())
                   .authorNickname(author.getNickname())
                   .authorAvatarKey(author.getAvatarOssKey());
        }

        return builder.build();
    }

    /** List<String> → JSON 字符串（写入 DB） */
    private String toJson(List<String> list) {
        if (list == null || list.isEmpty()) return "[]";
        try {
            return objectMapper.writeValueAsString(list);
        } catch (Exception e) {
            log.warn("JSON 序列化失败: {}", e.getMessage());
            return "[]";
        }
    }

    /** JSON 字符串 → List<String>（读出 DB） */
    private List<String> fromJson(String json) {
        if (json == null || json.isBlank() || "[]".equals(json)) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, new TypeReference<List<String>>() {});
        } catch (Exception e) {
            log.warn("JSON 反序列化失败: {}", e.getMessage());
            return Collections.emptyList();
        }
    }
}
