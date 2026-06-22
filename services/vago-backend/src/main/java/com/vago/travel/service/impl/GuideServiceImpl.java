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
import org.springframework.data.redis.core.RedisCallback;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Service
@Slf4j
public class GuideServiceImpl implements GuideService {

    // AI 向量化状态：0=PENDING，与 AiServiceImpl 中的常量保持一致
    private static final int AI_STATUS_PENDING = 0;

    // Redis key 前缀
    // 点赞计数 key：vago:guide:like:count:{uuid}  →  String（INCR）
    public static final String LIKE_COUNT_KEY_PREFIX = "vago:guide:like:count:";

    // 布隆过滤器 key：vago:guide:like:bloom:{uuid}  →  Bitmap（setBit / getBit）
    private static final String LIKE_BLOOM_PREFIX = "vago:guide:like:bloom:";

    // 撤回黑名单 key：vago:guide:like:unlike:users:{uuid}  →  Set<userUuid>（带 5 分钟 TTL）
    static final String LIKE_UNLIKE_BLACK_PREFIX = "vago:guide:like:unlike:users:";

    // 已点赞用户集合 key（仅供 LikeFlushTask 持久化使用，不在热读路径上）
    public static final String LIKE_USERS_KEY_PREFIX = "vago:guide:like:users:";

    // 布隆过滤器参数
    private static final int BLOOM_BITS = 10_000;          // 位图大小
    private static final int[] BLOOM_SEEDS = {31, 37, 131}; // k 个哈希种子
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
    public PageVO<GuideVO> listPublished(int page, int size, String currentUserUuid) {
        int offset = (page - 1) * size;
        List<Guide> guides = guideMapper.listPublished(size, offset);
        long total = guideMapper.countPublished();

        List<GuideVO> records = guides.stream()
                .map(g -> toVO(g, fetchAuthor(g.getUserUuid())))
                .collect(Collectors.toList());

        // 如果传入了用户 UUID，批量填充 liked 状态
        if (currentUserUuid != null && !records.isEmpty()) {
            fillLikedStatus(currentUserUuid, records);
        }

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
        List<GuideVO> records = guideMapper.listByUserUuid(userUuid)
                .stream().map(g -> toVO(g, author)).collect(Collectors.toList());

        // 批量填充 liked 状态
        if (!records.isEmpty()) {
            fillLikedStatus(userUuid, records);
        }
        return records;
    }

    @Override
    public GuideVO getDetail(String userUuid, String guideUuid) {
        Guide guide = getGuideOrThrow(guideUuid);

        // 浏览量 +1（非作者时才计）
        if (!guide.getUserUuid().equals(userUuid)) {
            guideMapper.incrementViewCount(guideUuid);
            guide.setViewCount(guide.getViewCount() == null ? 1 : guide.getViewCount() + 1);
        }

        // 从 Redis 读取实时点赞数，不存在则从 DB 查询并写入 Redis
        String countStr = stringRedisTemplate.opsForValue().get(LIKE_COUNT_KEY_PREFIX + guideUuid);
        if (countStr != null) {
            try {
                guide.setLikeCount(Integer.parseInt(countStr));
            } catch (NumberFormatException e) {
                log.warn("like count parse error: key={} val={}", guideUuid, countStr);
            }
        } else {
            int dbCount = guideMapper.countLikeByGuide(guideUuid);
            guide.setLikeCount(dbCount);
            stringRedisTemplate.opsForValue().setIfAbsent(
                    LIKE_COUNT_KEY_PREFIX + guideUuid, String.valueOf(dbCount));
        }

        // 点赞状态判定（布隆过滤器 + 黑名单二次确认）
        boolean liked = false;
        String bloomKey = LIKE_BLOOM_PREFIX + guideUuid;
        String blackKey = LIKE_UNLIKE_BLACK_PREFIX + guideUuid;
        if (bloomFilterCheck(bloomKey, userUuid)) {
            // 布隆判定「可能已点赞」，查黑名单排除撤回
            Boolean inBlack = stringRedisTemplate.opsForSet().isMember(blackKey, userUuid);
            liked = Boolean.FALSE.equals(inBlack);
        }

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
     * 点赞（布隆过滤器 + INCR 计数器）：
     * 1. 验证攻略存在
     * 2. 布隆过滤器判定 → 若已在且黑名单无此用户 → 幂等返回
     * 3. 布隆标记（SETBIT）
     * 4. 写 users Set（供 LikeFlushTask 持久化）
     * 5. SETNX 初始化 count + INCR
     */
    @Override
    public void like(String userUuid, String guideUuid) {
        Guide guide = getGuideOrThrow(guideUuid);

        String bloomKey = LIKE_BLOOM_PREFIX + guideUuid;
        String countKey = LIKE_COUNT_KEY_PREFIX + guideUuid;
        String blackKey = LIKE_UNLIKE_BLACK_PREFIX + guideUuid;

        // 布隆判定：如果已标记，检查是否在黑名单中
        if (bloomFilterCheck(bloomKey, userUuid)) {
            Boolean inBlack = stringRedisTemplate.opsForSet().isMember(blackKey, userUuid);
            if (Boolean.FALSE.equals(inBlack)) {
                log.debug("忽略重复点赞: userUuid={} guideUuid={}", userUuid, guideUuid);
                return;
            }
            // 从黑名单移除（重新点赞）
            stringRedisTemplate.opsForSet().remove(blackKey, userUuid);
        } else {
            // 首次点赞：布隆标记
            bloomFilterSet(bloomKey, userUuid);
        }

        // users Set（供 FlushTask 持久化 guide_likes 关系）
        stringRedisTemplate.opsForSet().add(LIKE_USERS_KEY_PREFIX + guideUuid, userUuid);

        // SETNX 初始化 count + INCR（原子自增）
        int dbCount = guide.getLikeCount() != null ? guide.getLikeCount() : 0;
        stringRedisTemplate.opsForValue().setIfAbsent(countKey, String.valueOf(dbCount));
        stringRedisTemplate.opsForValue().increment(countKey);
        log.debug("点赞: userUuid={} guideUuid={}", userUuid, guideUuid);
    }

    /**
     * 取消点赞（DECR + 写入撤回黑名单）：
     * 1. 验证攻略存在
     * 2. 黑名单 SADD（5 分钟 TTL），补偿布隆过滤器无法删除的缺陷
     * 3. users Set SREM（FlushTask 不再计入此人）
     * 4. DECR count，最小值 0
     */
    @Override
    public void unlike(String userUuid, String guideUuid) {
        getGuideOrThrow(guideUuid);

        String blackKey = LIKE_UNLIKE_BLACK_PREFIX + guideUuid;
        String countKey = LIKE_COUNT_KEY_PREFIX + guideUuid;

        // 写入撤回黑名单（带 5 分钟过期）
        stringRedisTemplate.opsForSet().add(blackKey, userUuid);
        stringRedisTemplate.expire(blackKey, 5, TimeUnit.MINUTES);

        // users Set SREM（FlushTask 不再将此用户刷入 guide_likes）
        stringRedisTemplate.opsForSet().remove(LIKE_USERS_KEY_PREFIX + guideUuid, userUuid);

        // DECR count，最小 0
        Long newCount = stringRedisTemplate.opsForValue().decrement(countKey);
        if (newCount != null && newCount < 0) {
            stringRedisTemplate.opsForValue().set(countKey, "0");
        }
        log.debug("取消点赞: userUuid={} guideUuid={}", userUuid, guideUuid);
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
     * 批量填充攻略 VO 的 liked 状态。
     *
     * 流程（Pipeline 两阶段，严禁穿透 DB）：
     *   ① Bloom Filter 批量判定（getBit pipeline）→ 拦截 90%+ 未点赞流量
     *   ② 对 Bloom 判定「可能已点赞」的 guide → 查撤回黑名单（SISMEMBER pipeline）
     *        - 黑名单中 → 已取消点赞 → false
     *        - 不在黑名单中 → 真正已点赞 → true
     */
    private void fillLikedStatus(String userUuid, List<GuideVO> records) {
        List<String> uuids = records.stream().map(GuideVO::getUuid).collect(Collectors.toList());
        int k = BLOOM_SEEDS.length;

        // ── 阶段①：Bloom Filter pipeline ──
        List<Object> bloomBits = stringRedisTemplate.executePipelined(
                (RedisCallback<Object>) connection -> {
                    for (String uuid : uuids) {
                        byte[] bloomKey = (LIKE_BLOOM_PREFIX + uuid).getBytes();
                        int[] offsets = bloomOffsets(userUuid);
                        for (int offset : offsets) {
                            connection.getBit(bloomKey, offset);
                        }
                    }
                    return null;
                });

        // 解析：连续 k 个 bit 为一组，全 1 才算「可能已点赞」
        List<String> maybeLiked = new ArrayList<>();
        for (int i = 0; i < uuids.size(); i++) {
            boolean allSet = true;
            for (int j = 0; j < k; j++) {
                Boolean bit = (Boolean) bloomBits.get(i * k + j);
                if (bit == null || !bit) {
                    allSet = false;
                    break;
                }
            }
            if (allSet) {
                maybeLiked.add(uuids.get(i));
            }
            // else: 布隆说未点赞 → 必定未点赞，直接跳过（拦截 90%+ 流量）
        }

        // ── 阶段②：黑名单二次确认 pipeline ──
        Set<String> likedSet = new HashSet<>();
        if (!maybeLiked.isEmpty()) {
            List<Object> blackResults = stringRedisTemplate.executePipelined(
                    (RedisCallback<Object>) connection -> {
                        for (String uuid : maybeLiked) {
                            byte[] blackKey = (LIKE_UNLIKE_BLACK_PREFIX + uuid).getBytes();
                            connection.sIsMember(blackKey, userUuid.getBytes());
                        }
                        return null;
                    });

            for (int i = 0; i < maybeLiked.size(); i++) {
                Boolean inBlack = (Boolean) blackResults.get(i);
                if (Boolean.FALSE.equals(inBlack)) {
                    likedSet.add(maybeLiked.get(i));
                }
                // 在黑名单中 → 用户已撤回 → 不加入 likedSet
            }
        }

        // ── 设置 VO ──
        for (GuideVO vo : records) {
            if (likedSet.contains(vo.getUuid())) {
                vo.setLiked(true);
            }
        }
    }

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

    // ── 布隆过滤器工具 ──────────────────────────────────────────────────────────

    /** 计算 k 个哈希桶下标 */
    private int[] bloomOffsets(String userUuid) {
        int[] offsets = new int[BLOOM_SEEDS.length];
        for (int i = 0; i < BLOOM_SEEDS.length; i++) {
            int h = 0;
            for (int j = 0; j < userUuid.length(); j++) {
                h = BLOOM_SEEDS[i] * h + userUuid.charAt(j);
            }
            offsets[i] = (h & Integer.MAX_VALUE) % BLOOM_BITS;
        }
        return offsets;
    }

    /** 布隆过滤器：标记（SETBIT k 个位） */
    private void bloomFilterSet(String bloomKey, String userUuid) {
        int[] offsets = bloomOffsets(userUuid);
        for (int offset : offsets) {
            stringRedisTemplate.opsForValue().setBit(bloomKey, offset, true);
        }
    }

    /** 布隆过滤器：判定（GETBIT k 个位，全 1 返回 true） */
    private boolean bloomFilterCheck(String bloomKey, String userUuid) {
        int[] offsets = bloomOffsets(userUuid);
        for (int offset : offsets) {
            Boolean bit = stringRedisTemplate.opsForValue().getBit(bloomKey, offset);
            if (bit == null || !bit) return false;
        }
        return true;
    }

    /**
     * 批量查询攻略列表（供收藏夹内展示用，不触发浏览量+1）。
     * 批量加载所有关联作者，按传入 ID 顺序返回，不存在的 ID 被跳过。
     */
    @Override
    public List<GuideVO> listByIds(String userUuid, List<String> uuids) {
        if (uuids == null || uuids.isEmpty()) {
            return Collections.emptyList();
        }
        // 1. 批量查询攻略
        List<Guide> guides = guideMapper.selectByUuids(uuids);
        if (guides.isEmpty()) {
            return Collections.emptyList();
        }

        // 2. 批量加载作者（去重）
        List<String> authorUuids = guides.stream()
                .map(Guide::getUserUuid)
                .distinct()
                .collect(Collectors.toList());
        List<User> authors = userMapper.selectByUuids(authorUuids);
        Map<String, User> authorMap = authors.stream()
                .collect(Collectors.toMap(User::getUuid, u -> u));

        // 3. 按传入 uuids 顺序组装 VO（不存在的跳过）
        Map<String, Guide> guideMap = guides.stream()
                .collect(Collectors.toMap(Guide::getUuid, g -> g));
        List<GuideVO> result = new ArrayList<>();
        for (String uuid : uuids) {
            Guide g = guideMap.get(uuid);
            if (g != null) {
                result.add(toVO(g, authorMap.get(g.getUserUuid())));
            }
        }
        return result;
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
