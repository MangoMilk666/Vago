package com.vago.travel.task;

import com.vago.travel.mapper.GuideMapper;
import com.vago.travel.service.impl.GuideServiceImpl;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.Cursor;
import org.springframework.data.redis.core.ScanOptions;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.Set;

/**
 * 点赞数据异步刷回任务。
 *
 * Redis 是点赞的实时权威存储，MySQL（guide_likes 表 + guides.like_count）为持久化存储。
 * 每 5 分钟将 Redis 中的点赞计数和点赞关系批量同步到 MySQL，保证最终一致。
 *
 * 同步策略（全量替换）：
 *   1. 从 `guides.like_count` 写入 Redis 计数
 *   2. 从 `SISMEMBER` 写入 `guide_likes` 表（先清空该攻略的所有记录再逐条 INSERT IGNORE）
 */
@Component
@Slf4j
public class LikeFlushTask {

    private static final String COUNT_PATTERN = GuideServiceImpl.LIKE_COUNT_KEY_PREFIX + "*";
    private static final int    PREFIX_LENGTH = GuideServiceImpl.LIKE_COUNT_KEY_PREFIX.length();

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Autowired
    private GuideMapper guideMapper;

    /**
     * 每 5 分钟将 Redis 中标脏的点赞数据全量同步到 MySQL。
     * 应用启动 60s 后首次执行，之后每次执行结束再等 5 分钟（fixedDelay 避免任务堆积）。
     */
    @Scheduled(initialDelay = 60_000, fixedDelay = 300_000)
    public void flush() {
        int flushed = 0;
        int failed  = 0;

        ScanOptions opts = ScanOptions.scanOptions()
                .match(COUNT_PATTERN)
                .count(100)
                .build();

        try (Cursor<String> cursor = stringRedisTemplate.scan(opts)) {
            while (cursor.hasNext()) {
                String key       = cursor.next();
                String guideUuid = key.substring(PREFIX_LENGTH);
                String countStr  = stringRedisTemplate.opsForValue().get(key);
                if (countStr == null) continue;

                try {
                    int count = Integer.parseInt(countStr);

                    // 1. 刷点赞数到 guides.like_count
                    guideMapper.updateLikeCount(guideUuid, count);

                    // 2. 刷点赞关系到 guide_likes 表
                    String usersKey = GuideServiceImpl.LIKE_USERS_KEY_PREFIX + guideUuid;
                    Set<String> users = stringRedisTemplate.opsForSet().members(usersKey);

                    if (users != null) {
                        // 全量替换：先清空该攻略的所有历史记录
                        guideMapper.deleteAllLikes(guideUuid);
                        // 再逐条插入 Redis 中最新的用户集合
                        for (String userUuid : users) {
                            guideMapper.insertIgnoreLike(guideUuid, userUuid);
                        }
                    }

                    flushed++;
                } catch (NumberFormatException e) {
                    log.warn("无效的点赞计数 val={} key={}", countStr, key);
                    failed++;
                } catch (Exception e) {
                    log.error("刷写失败 uuid={}", guideUuid, e);
                    failed++;
                }
            }
        } catch (Exception e) {
            log.error("Redis SCAN 失败", e);
            return;
        }

        if (flushed > 0 || failed > 0) {
            log.info("点赞数据刷写完成: flushed={} failed={}", flushed, failed);
        }
    }
}
