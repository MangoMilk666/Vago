package com.vago.travel.mapper;

import com.vago.travel.model.entity.Guide;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface GuideMapper {
    /**
     * 新增攻略
     * @param guide, ai_status允许为NULL
     * @return
     */
    @Insert("""
            INSERT INTO guides
              (uuid, user_uuid, title, destination, cover_image_key, image_keys,
               content, tags, view_count, like_count, status, ai_status, created_at, updated_at)
            VALUES
              (#{uuid}, #{userUuid}, #{title}, #{destination}, #{coverImageKey}, #{imageKeys},
               #{content}, #{tags}, 0, 0, #{status}, #{aiStatus,jdbcType=TINYINT}, #{createdAt}, #{updatedAt})
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(Guide guide);

    /** 公开攻略列表（分页） */
    @Select("""
            SELECT * FROM guides
            WHERE status = 1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT #{size} OFFSET #{offset}
            """)
    List<Guide> listPublished(@Param("size") int size, @Param("offset") int offset);

    /** 公开攻略总数 */
    @Select("SELECT COUNT(*) FROM guides WHERE status = 1 AND deleted_at IS NULL")
    long countPublished();

    /** 我本人的攻略（含草稿） */
    @Select("""
            SELECT * FROM guides
            WHERE user_uuid = #{userUuid} AND deleted_at IS NULL
            ORDER BY created_at DESC
            """)
    List<Guide> listByUserUuid(String userUuid);

    /**
     * 根据uuid查找帖子
     * @param uuid
     * @return
     */
    @Select("SELECT * FROM guides WHERE uuid = #{uuid} AND deleted_at IS NULL")
    Guide getByUuid(String uuid);

    /**
     * 更新攻略
     * @param guide
     * @return
     */
    @Update("""
            UPDATE guides SET
              title           = #{title},
              destination     = #{destination},
              cover_image_key = #{coverImageKey},
              image_keys      = #{imageKeys},
              content         = #{content},
              tags            = #{tags},
              status          = #{status},
              updated_at      = NOW(3)
            WHERE uuid = #{uuid}
            """)
    int update(Guide guide);

    /** 浏览量 +1 */
    @Update("UPDATE guides SET view_count = view_count + 1 WHERE uuid = #{uuid}")
    int incrementViewCount(String uuid);

    /** 点赞 +1（直接写 DB，已被 Redis flush 方案替代，保留供回退） */
    @Update("UPDATE guides SET like_count = like_count + 1 WHERE uuid = #{uuid}")
    int incrementLikeCount(String uuid);

    /** 将 Redis 中的点赞计数批量写回 DB（由 LikeFlushJob 调用） */
    @Update("UPDATE guides SET like_count = #{count} WHERE uuid = #{uuid} AND deleted_at IS NULL")
    int updateLikeCount(@Param("uuid") String uuid, @Param("count") int count);

    /**
     * 软删除
     * @param uuid
     * @return
     */
    @Update("UPDATE guides SET deleted_at = NOW(3), updated_at = NOW(3) WHERE uuid = #{uuid}")
    int softDelete(String uuid);

    /**
     * 单独更新 AI 向量化状态（由 AiServiceImpl 异步回写）。
     * aiStatus 为 null 时将数据库字段置为 NULL（用于草稿降级场景）。
     */
    @Update("UPDATE guides SET ai_status = #{aiStatus,jdbcType=TINYINT}, updated_at = NOW(3) WHERE uuid = #{uuid}")
    int updateAiStatus(@Param("uuid") String uuid, @Param("aiStatus") Integer aiStatus);

    /**
     * 批量查询攻略（用于收藏夹内攻略列表，解决 N+1 问题）。
     * MyBatis 直接传入 List，自动展开为 IN 子句。
     */
    @Select("<script>" +
            "SELECT * FROM guides WHERE uuid IN " +
            "<foreach item='uuid' collection='uuids' open='(' separator=',' close=')'>" +
            "#{uuid}</foreach> AND deleted_at IS NULL" +
            "</script>")
    List<Guide> selectByUuids(@Param("uuids") List<String> uuids);
}
