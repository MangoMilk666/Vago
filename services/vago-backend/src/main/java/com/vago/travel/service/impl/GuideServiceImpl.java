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
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
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

    @Autowired
    private GuideMapper guideMapper;

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private AiService aiService;

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

        return toVO(guide, fetchAuthor(guide.getUserUuid()));
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

    @Override
    public void like(String guideUuid) {
        // 简单实现：直接 +1；生产可加防重点赞（Redis Set）
        guideMapper.incrementLikeCount(guideUuid);
    }

    // ── 私有工具 ─────────────────────────────────────────────────────────────

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

    /** Guide 实体 → GuideVO（含作者信息） */
    private GuideVO toVO(Guide g, User author) {
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
