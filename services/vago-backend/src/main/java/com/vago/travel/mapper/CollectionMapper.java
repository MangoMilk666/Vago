package com.vago.travel.mapper;

import com.vago.travel.model.dto.CollectionUpdateDTO;
import com.vago.travel.model.entity.Collection;
import com.vago.travel.model.entity.CollectionItem;

import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface CollectionMapper {

    @Insert("insert into collections (uuid, user_uuid, name, type, description, created_at, updated_at) " +
            "VALUES (#{uuid}, #{userUuid}, #{name}, #{type}, #{description}, #{createdAt}, #{updatedAt})")
    void insert(Collection c);

    @Select("select uuid, user_uuid, name, type, description, created_at, updated_at from collections where uuid = #{uuid}")
    Collection getByUuid(String uuid);

    @Update("update collections set name = #{name}, description = #{description}, updated_at = NOW(3) where uuid = #{uuid}")
    void update(CollectionUpdateDTO dto);

    /** 删除指定收藏夹下的所有收藏记录 */
    @Delete("delete from collection_items where collection_uuid = #{uuid}")
    void deleteItemsByCollection(String uuid);

    @Delete("delete from collections where uuid = #{uuid}")
    void deleteByUuid(String uuid);

    @Select("select uuid, user_uuid, name, type, description, created_at, updated_at from collections " +
            "where user_uuid = #{userUuid} order by created_at desc")
    List<Collection> getListByUserid(String userUuid);

    /**
     * 收藏攻略到指定收藏夹。
     * 防重复由数据库 UNIQUE KEY (collection_uuid, guide_uuid) 兜底。
     */
    @Insert("insert into collection_items(uuid, collection_uuid, guide_uuid, user_uuid, note, created_at) " +
            "VALUES (#{uuid}, #{collectionUuid}, #{guideUuid}, #{userUuid}, #{note}, #{createdAt})")
    void saveInto(CollectionItem item);

    /** 从收藏夹移除指定攻略 */
    @Delete("delete from collection_items where collection_uuid=#{collectionUuid} and guide_uuid=#{guideUuid}")
    void deleteItem(String collectionUuid, String guideUuid);

    /** 获取某收藏夹内的攻略 UUID 列表，按收藏时间降序 */
    @Select("select guide_uuid from collection_items " +
            "where collection_uuid = #{collectionUuid} order by created_at desc")
    List<String> getItemsByCollectionId(String collectionUuid);

    /** 查询某攻略被当前用户收藏到了哪些收藏夹 */
    @Select("select collection_uuid from collection_items " +
            "where guide_uuid=#{guideUuid} and user_uuid=#{userUuid}")
    List<String> inWhichCollections(String guideUuid, String userUuid);

    /**
     * 检查某攻略是否已在指定收藏夹中（防重复）。
     * 返回 >0 表示已存在。
     */
    @Select("select count(1) from collection_items " +
            "where collection_uuid=#{collectionUuid} and guide_uuid=#{guideUuid}")
    int countItem(String collectionUuid, String guideUuid);
}
