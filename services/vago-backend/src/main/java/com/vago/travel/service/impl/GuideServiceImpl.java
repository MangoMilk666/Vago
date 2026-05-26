package com.vago.travel.service.impl;

import cn.hutool.core.util.IdUtil;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
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

    @Autowired
    private GuideMapper guideMapper;

    @Autowired
    private UserMapper userMapper;

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
     * 新增攻略
     */
    @Override
    public GuideVO create(String userUuid, GuideCreateDTO dto) {
        LocalDateTime now = LocalDateTime.now();
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
                .status(dto.getStatus() != null ? dto.getStatus() : 1)
                .createdAt(now)
                .updatedAt(now)
                .build();

        guideMapper.insert(guide);
        log.info("攻略创建: uuid={}, userUuid={}", guide.getUuid(), userUuid);
        return toVO(guide, fetchAuthor(userUuid));
    }

    @Override
    public GuideVO update(String userUuid, String guideUuid, GuideUpdateDTO dto) {
        Guide guide = getGuideOrThrow(guideUuid);
        checkOwner(guide, userUuid);
        // 复制dto中的成员变量
        BeanUtils.copyProperties(dto, guide);
        if (dto.getTitle()          != null) guide.setTitle(dto.getTitle());
        if (dto.getDestination()    != null) guide.setDestination(dto.getDestination());
        if (dto.getCoverImageKey()  != null) guide.setCoverImageKey(dto.getCoverImageKey());
        if (dto.getImageKeys()      != null) guide.setImageKeys(toJson(dto.getImageKeys()));
        if (dto.getContent()        != null) guide.setContent(dto.getContent());
        if (dto.getTags()           != null) guide.setTags(toJson(dto.getTags()));
        if (dto.getStatus()         != null) guide.setStatus(dto.getStatus());

        guideMapper.update(guide);
        log.info("攻略更新: uuid={}", guideUuid);
        return toVO(guideMapper.getByUuid(guideUuid), fetchAuthor(userUuid));
    }

    @Override
    public void delete(String userUuid, String guideUuid) {
        Guide guide = getGuideOrThrow(guideUuid);
        checkOwner(guide, userUuid);
        guideMapper.softDelete(guideUuid);
        log.info("攻略删除: uuid={}", guideUuid);
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
