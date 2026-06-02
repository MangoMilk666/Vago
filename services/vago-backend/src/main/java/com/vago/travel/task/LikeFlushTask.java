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

/**
 * 点赞计数异步写回任务。
 *
 * Redis 是点赞计数的实时权威，MySQL 为持久化存储。
 * 每 5 分钟将 Redis 中所有攻略的点赞数批量同步到 MySQL，保证最终一致。
 * 使用 SCAN 而非 KEYS，避免 key 量大时阻塞 Redis。
 */
@Component
@Slf4j
public class LikeFlushTask {

    private static final String SCAN_PATTERN = GuideServiceImpl.LIKE_COUNT_KEY_PREFIX + "*";
    private static final int    PREFIX_LENGTH = GuideServiceImpl.LIKE_COUNT_KEY_PREFIX.length();

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Autowired
    private GuideMapper guideMapper;

    /**
     * 把这 5 分钟内所有产生过点赞变化的攻略 Key 集中扫描出来，批量或者分批更新回 MySQL
     * 应用启动 60s 后首次执行，之后每次执行结束再等 5 分钟（fixedDelay 避免任务堆积）。
     */
    @Scheduled(initialDelay = 60_000, fixedDelay = 300_000)
    public void flush() {
        int flushed = 0;
        int failed  = 0;
        // SCAN 的目的：用流式、分步的方式替代 KEYS。每次只看一小批（比如 count(100)），走走停停，给别的高频线上请求留出喘息和插队的时间
        ScanOptions opts = ScanOptions.scanOptions()
                .match(SCAN_PATTERN)
                .count(100)
                .build();
        // try-with-resources, 自动调用 cursor.close()
        try (Cursor<String> cursor = stringRedisTemplate.scan(opts)) {
            while (cursor.hasNext()) {
                String key       = cursor.next();
                String guideUuid = key.substring(PREFIX_LENGTH);
                String countStr  = stringRedisTemplate.opsForValue().get(key);
                if (countStr == null) continue;

                try {
                    int count = Integer.parseInt(countStr);
                    int rows  = guideMapper.updateLikeCount(guideUuid, count);
                    if (rows > 0) flushed++;
                } catch (NumberFormatException e) {
                    log.warn("点赞数刷新写入DB失败: 无效的 count val={} key={}", countStr, key);
                    failed++;
                } catch (Exception e) {
                    log.error("点赞数刷新写入DB失败: DB write failed for uuid={}", guideUuid, e);
                    failed++;
                }
            }
        } catch (Exception e) {
            log.error("点赞数刷新写入DB失败: Redis SCAN failed", e);
            return;
        }

        if (flushed > 0 || failed > 0) {
            log.info("点赞数写入DB完成: flushed={} failed={}", flushed, failed);
        }
    }
}
